(() => {
  const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const T = new Int16Array(128).fill(-1);
  for (let i=0;i<64;i++) T[CHARS.charCodeAt(i)] = i;
  function b64decode(s) {
    let n=0,k=0,a=[];
    for (let i=0;i<s.length;i++) { const c=s.charCodeAt(i); if(c===61) break;
      if(c>127 || T[c]<0) continue; n=(n<<6)|T[c]; k+=6;
      if(k>=8) { k-=8; a.push((n>>>k)&255); }
    }
    return a;
  }
  function textDecode(b) {
    let a=[];
    for(let i=0;i<b.length;) { let c=b[i++];
      a.push(c<128?c:c<224?((c&31)<<6)|(b[i++]&63):c<240?((c&15)<<12)|((b[i++]&63)<<6)|(b[i++]&63):((c&7)<<18)|((b[i++]&63)<<12)|((b[i++]&63)<<6)|(b[i++]&63));
    }
    let parts=[];
    for(let i=0;i<a.length;i+=6000)parts.push(String.fromCodePoint(...a.slice(i,i+6000)));
    return parts.join("");
  }
  function textEncode(s) {
    let a=[];
    for(let i=0;i<s.length;i++) { const c=s.codePointAt(i); if(c>65535)i++;
      if(c<128)a.push(c);
      else if(c<2048)a.push(192|(c>>6),128|(c&63));
      else if(c<65536)a.push(224|(c>>12),128|((c>>6)&63),128|(c&63));
      else a.push(240|(c>>18),128|((c>>12)&63),128|((c>>6)&63),128|(c&63));
    }
    return a;
  }
  function unpack(bytes) {
    const u=p=>bytes[p]|(bytes[p+1]<<8),
          v=p=>(bytes[p]|(bytes[p+1]<<8)|(bytes[p+2]<<16)|(bytes[p+3]<<24))>>>0;
    let p=0, files={};
    while(v(p)===0x04034b50) {
      const size=v(p+18),nl=u(p+26),el=u(p+28);
      if(u(p+8)!==0 || u(p+6)&8)throw Error("Compressed/descriptor ZIP not supported");
      const name=textDecode(bytes.slice(p+30,p+30+nl)), start=p+30+nl+el;
      files[name]=textDecode(bytes.slice(start,start+size)); p=start+size;
    }
    if(Object.keys(files).length!==14)throw Error("Expected exactly 14 markdown docs");
    return files;
  }
  const CT=new Uint32Array(256);
  for(let i=0;i<256;i++) { let c=i;for(let j=0;j<8;j++)c=c&1?0xedb88320^(c>>>1):c>>>1;CT[i]=c>>>0; }
  function crc32(a){let c=0xffffffff;for(const x of a)c=CT[(c^x)&255]^(c>>>8);return(c^0xffffffff)>>>0;}
  function repack(files) {
    const bytes=[],entries=[];
    const put=(...xs)=>bytes.push(...xs),w16=x=>put(x&255,(x>>>8)&255),w32=x=>put(x&255,(x>>>8)&255,(x>>>16)&255,(x>>>24)&255);
    for(const [path,content] of Object.entries(files)) {
      const n=textEncode(path),d=textEncode(content),c=crc32(d),start=bytes.length;
      put(80,75,3,4);w16(20);w16(2048);w16(0);w16(0);w16(0);w32(c);w32(d.length);w32(d.length);w16(n.length);w16(0);put(...n);put(...d);
      entries.push({n,d,c,start});
    }
    const offset=bytes.length;
    for(const e of entries) {
      put(80,75,1,2);w16(20);w16(20);w16(2048);w16(0);w16(0);w16(0);w32(e.c);w32(e.d.length);w32(e.d.length);
      w16(e.n.length);w16(0);w16(0);w16(0);w16(0);w32(0);w32(e.start);put(...e.n);
    }
    const size=bytes.length-offset;
    put(80,75,5,6);w16(0);w16(0);w16(entries.length);w16(entries.length);w32(size);w32(offset);w16(0);
    return bytes;
  }
  function b64encode(a) {
    let o=[];
    for(let i=0;i<a.length;i+=3) {
      let n=(a[i]<<16)|((a[i+1]||0)<<8)|(a[i+2]||0);
      o.push(CHARS[(n>>>18)&63]+CHARS[(n>>>12)&63]+
        (i+1<a.length?CHARS[(n>>>6)&63]:"=")+(i+2<a.length?CHARS[n&63]:"="));
    }
    return o.join("");
  }
  function extract(document, label) {
    const a="## ["+label+"]",b="## [/"+label+"]";
    const start=document.indexOf(a),end=document.indexOf(b);
    if(start<0||end<start)throw Error("Missing section "+label);
    return document.slice(start+a.length,end).trim();
  }
  const modes={
    live2d_bust_up:"MODE_LIVE2D_BUST_UP",
    live2d_upper:"MODE_LIVE2D_UPPER",
    live2d_full:"MODE_LIVE2D_FULL",
    inochi2d_upper:"MODE_INOCHI2D_UPPER",
    inochi2d_full:"MODE_INOCHI2D_FULL",
    "3d":"MODE_3D"
  };
  function update(files, mode, asset, master) {
    const is3d=mode==="3d";
    const common=extract(master,is3d?"GLOBAL_3D":"GLOBAL_2D");
    const details=extract(master,asset.toUpperCase()+"_"+(is3d?"3D":"2D"));
    const modeSpecific=extract(master,modes[mode]);
    const review=extract(master,is3d?"REVIEW_3D":"REVIEW_2D");
    const start="## [EXPLICIT_DRAWING_STEPS_V1]";
    const end="## [/EXPLICIT_DRAWING_STEPS_V1]";
    const reviewStart="## [REAL_VISUAL_REVIEW_V1]";
    const reviewEnd="## [/REAL_VISUAL_REVIEW_V1]";
    const steps=[start,
      "### 실제로 한 장씩 그릴 원화의 형태·가림·측면 관계 — 반드시 순서대로 실행",
      "**단순 파일 이름 목록이 아니다. 각 항목은 실제 그릴 내용, 어느 면을 감추고 보존할지, 완성 조건이다.**",
      common,details,modeSpecific,end].join("\n\n");
    const checks=[reviewStart,
      "### 실제 합성과 옆모습·목 연결을 보는 구체적 완성 판정",
      review,reviewEnd].join("\n\n");
    function replaceSlot(path,s,e,body) {
      const d=files[path];
      if(typeof d!=="string")throw Error("Missing "+path);
      const i=d.indexOf(s),j=d.indexOf(e);
      let newDoc;
      if(i>=0&&j>=i) {
        const until=j+e.length;
        newDoc=d.slice(0,i)+body+d.slice(until);
      } else if(i>=0||j>=0)throw Error("Half-written recipe "+path);
      else newDoc=d.trimEnd()+"\n\n"+body+"\n";
      files[path]=newDoc;
    }
    replaceSlot("02_ADVANCED_PARTS.md",start,end,steps);
    replaceSlot("07_REVIEW_BEFORE_FINAL_ZIP.md",reviewStart,reviewEnd,checks);
    // This frontpage instruction points the image AI to the actionable full
    // recipes. Do not print the same whole recipe in all fourteen files.
    for(const name of ["00_MASTER_FIRST.md","00_READ_FIRST.md"]) {
      const sign="**[실제 원화 작화 방식: 02_ADVANCED_PARTS.md의 EXPLICIT_DRAWING_STEPS_V1을 반드시 먼저 열어 따르며, 07_REVIEW_BEFORE_FINAL_ZIP.md의 REAL_VISUAL_REVIEW_V1로 실제 그림을 비교한다.]**";
      let d=files[name];
      if(!d.includes(sign)) {
        const p=d.indexOf("\n");
        files[name]=d.slice(0,p+1)+"\n"+sign+"\n"+d.slice(p+1);
      }
    }
    if(Object.keys(files).length!==14)throw Error("Unexpected markdown members after edit");
    return {files,metadata:{mode,asset,detailed_recipe_lines:steps.split("\n").length,
             review_lines:checks.split("\n").length,
             has_neck_guide:details.includes("neck.png"),
             markers:{"02":files["02_ADVANCED_PARTS.md"].includes(start),
                      "07":files["07_REVIEW_BEFORE_FINAL_ZIP.md"].includes(reviewStart)}}};
  }
  return {b64decode,textDecode,textEncode,unpack,repack,b64encode,extract,update};
})()