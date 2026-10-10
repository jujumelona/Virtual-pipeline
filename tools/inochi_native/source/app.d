// BSD-2 SDK 0.8.7 native Inochi puppet exporter.
// Requires an active SDL2 OpenGL context; NEVER forges INP magic or metadata.
module app;
import inochi2d;
import inochi2d.core.param.binding : DeformationParameterBinding;
import inochi2d.core.nodes.drivers.simplephysics : SimplePhysics;
import inochi2d.core.texture : ShallowTexture, Texture, inTexPremultiply;
import bindbc.opengl : loadOpenGL;
import std.json;
import std.file : readText, write, exists;
import std.conv : to;
import std.exception : enforce;
import std.stdio : writeln;
import std.path : absolutePath;
import std.math : isFinite;

extern(C) {
    int SDL_Init(uint flags);
    void SDL_Quit();
    void* SDL_CreateWindow(const(char)* title, int x, int y, int w, int h, uint flags);
    void SDL_DestroyWindow(void*);
    void* SDL_GL_CreateContext(void*);
    void SDL_GL_DeleteContext(void*);
    int SDL_GL_MakeCurrent(void*, void*);
}
enum uint SDL_INIT_VIDEO = 0x20;
enum uint SDL_WINDOW_HIDDEN_OPENGL = 0x0000000A;

float number(JSONValue v) {
    float f = to!float(v.toString());
    enforce(isFinite(f), "non-finite numeric value in puppet interchange");
    return f;
}
vec2 xy(JSONValue v) {
    enforce(v.type == JSONType.array && v.array.length == 2, "expected vec2");
    return vec2(number(v[0]), number(v[1]));
}

double frozenTime() { return 0.0; }

int main(string[] args) {
    enforce(args.length == 4, "usage: vtuber-inochi-native spec.json avatar.inp native_report.json");
    auto spec = parseJSON(readText(args[1]));
    enforce(spec["schema"].str == "vtuber-puppet-interchange-v1", "unknown interchange schema");
    int canvasW = cast(int)number(spec["canvas"][0]);
    int canvasH = cast(int)number(spec["canvas"][1]);
    enforce(canvasW > 0 && canvasH > 0 && canvasW <= 8192 && canvasH <= 8192,
            "unsafe Inochi canvas");

    enforce(SDL_Init(SDL_INIT_VIDEO) == 0, "SDL2 video initialization failed");
    scope(exit) SDL_Quit();
    void* window = SDL_CreateWindow("Inochi native export", 0, 0, 48, 48,
                                   SDL_WINDOW_HIDDEN_OPENGL);
    enforce(window !is null, "SDL2 hidden OpenGL context unavailable");
    scope(exit) SDL_DestroyWindow(window);
    void* glContext = SDL_GL_CreateContext(window);
    enforce(glContext !is null, "SDL2 OpenGL context creation failed");
    scope(exit) SDL_GL_DeleteContext(glContext);
    enforce(SDL_GL_MakeCurrent(window, glContext) == 0, "SDL2 OpenGL make-current failed");
    loadOpenGL();
    inInit(&frozenTime);

    auto puppet = new Puppet();
    puppet.meta.name = "VTuber Commercial Avatar";
    puppet.meta.rigger = "VTuber Pipeline (official Inochi SDK 0.8.7)";
    Part[string] parts;
    size_t meshVertices = 0;
    foreach (item; spec["mesh"].array) {
        string name = item["semantic_id"].str;
        enforce((name !in parts), "duplicate part semantic id");
        auto vertices = item["vertices_xy"].array;
        auto uvs = item["uv"].array;
        auto triangles = item["triangles"].array;
        enforce(vertices.length >= 3 && vertices.length <= ushort.max,
                "invalid mesh vertex count");
        enforce(uvs.length == vertices.length && triangles.length > 0, "invalid mesh UV/triangle contract");
        MeshData data;
        foreach (i, vertex; vertices) {
            vec2 p = xy(vertex);
            vec2 uv = xy(uvs[i]);
            enforce(uv.x >= 0 && uv.x <= 1 && uv.y >= 0 && uv.y <= 1,
                    "part UV lies outside atlas");
            // SDK 0.8.7 Camera.matrix/createQuadMesh use centered Y-down
            // coordinates. Keep image Y direction; flipping mirrors the model.
            data.add(vec2(p.x - canvasW * .5f, p.y - canvasH * .5f), uv);
        }
        foreach (triangle; triangles) {
            enforce(triangle.array.length == 3, "invalid triangle");
            foreach (index; triangle.array) {
                uint idx = cast(uint)number(index);
                enforce(idx < vertices.length, "triangle index outside part mesh");
                data.indices ~= cast(ushort)idx;
            }
        }
        data.fixWinding();
        enforce(data.isReady(), "triangular mesh not ready");
        auto path = item["rgba_png"].str;
        enforce(exists(path), "missing observable part PNG: " ~ path);
        // PNG artwork uses straight alpha. SDK 0.8.7 Part shaders/blending
        // consume premultiplied RGB, and the INP serializer preserves those
        // bytes. Convert once before upload; the SDK INP loader does not.
        auto shallow = ShallowTexture(path, 4);
        inTexPremultiply(shallow.data, shallow.channels);
        auto texture = new Texture(shallow);
        auto part = new Part(data, [texture], puppet.root);
        part.name = name;
        part.zSort = number(item["z_order"]);
        parts[name] = part;
        meshVertices += vertices.length;
    }
    enforce(parts.length > 0, "Inochi cannot export an empty puppet");

    Parameter[string] parameters;
    size_t boundKeyforms = 0;
    foreach (name, endpoints; spec["parameters"].object) {
        auto values = endpoints.array;
        enforce(values.length == 3, "one-dimensional parameter expected");
        float lo = number(values[0]), mid = number(values[1]), hi = number(values[2]);
        enforce(lo <= mid && mid <= hi && lo < hi, "invalid parameter range");
        auto parameter = new Parameter(name, false);
        parameter.min = vec2(lo, 0);
        parameter.max = vec2(hi, 0);
        parameter.defaults = vec2(mid, 0);
        parameter.value = parameter.defaults;
        if (mid > lo && mid < hi) {
            parameter.axisPoints[0] = [0.0f, (mid-lo)/(hi-lo), 1.0f];
        } else {
            parameter.axisPoints[0] = [0.0f, 1.0f];
        }
        puppet.parameters ~= parameter;
        parameters[name] = parameter;
    }
    foreach (entry; spec["keyforms"].array) {
        string name = entry["semantic_id"].str;
        enforce((name in parts) !is null, "keyform points to absent part");
        auto part = parts[name];
        foreach (paramName, deltaSet; entry["deltas"].object) {
            enforce((paramName in parameters) !is null, "binding target parameter absent");
            auto param = parameters[paramName];
            auto binding = cast(DeformationParameterBinding)param.getOrAddBinding(part, "deform", false);
            enforce(binding !is null, "SDK failed to create deformation binding");
            auto endpointNames = param.axisPoints[0].length == 3
                               ? ["min", "default", "max"]
                               : ["min", "max"];
            foreach (i, endpointName; endpointNames) {
                auto sourceDeltas = deltaSet[endpointName].array;
                enforce(sourceDeltas.length == part.vertices.length,
                        "parameter deformation point count mismatch");
                vec2[] deltas;
                deltas.length = sourceDeltas.length;
                foreach (j, delta; sourceDeltas) {
                    vec2 d = xy(delta);
                    // Translation changes the origin, not delta direction.
                    deltas[j] = d;
                }
                binding.update(vec2u(cast(uint)i, 0), deltas);
                if (endpointName != "default") boundKeyforms++;
            }
        }
    }
    size_t physicsCount = 0;
    foreach (spring; spec["physics"].array) {
        string partName = spring["semantic_id"].str;
        string paramName = spring["target_parameter"].str;
        enforce((partName in parts) !is null, "spring attached to nonexistent mesh");
        enforce((paramName in parameters) !is null, "spring drives missing parameter");
        enforce(parameters[paramName].hasAnyBinding(parts[partName]),
                "spring parameter has no real mesh deformation");
        auto node = new SimplePhysics(puppet.root);
        node.name = "Spring " ~ partName;
        node.param(parameters[paramName]);
        node.frequency = number(spring["stiffness"]) * .2f;
        node.angleDamping = number(spring["damping"]);
        node.length = 80.0f;
        physicsCount++;
    }
    enforce(boundKeyforms > 0 && physicsCount > 0,
            "native puppet must include actual keyed vertex deformations and secondary physics");
    puppet.populateTextureSlots();
    inWriteINPPuppet(puppet, args[2]);
    enforce(exists(args[2]), "official SDK produced no INP file");

    // SDK-native deserialization is the acceptance gate, not just a header.
    auto roundtrip = inLoadPuppet(args[2]);
    size_t verifiedBindings = 0;
    foreach (parameter; roundtrip.parameters) {
        verifiedBindings += parameter.bindings.length;
    }
    enforce(verifiedBindings > 0 && roundtrip.getAllParts().length > 0,
            "SDK reimport lost the mesh deformation bindings");
    auto report = [
        "sdk_native_write": JSONValue(true),
        "sdk_roundtrip_read": JSONValue(true),
        "sdk_version": JSONValue("0.8.7"),
        "bound_keyforms_count": JSONValue(cast(long)boundKeyforms),
        "mesh_vertices_count": JSONValue(cast(long)meshVertices),
        "physics_bindings_count": JSONValue(cast(long)physicsCount),
        "sdk_reimport_binding_count": JSONValue(cast(long)verifiedBindings),
        "inp_format": JSONValue("INP1"),
        "texture_alpha_mode": JSONValue("premultiplied"),
    ];
    write(args[3], JSONValue(report).toString());
    writeln("inochi-native-sdk-export-pass");
    return 0;
}
