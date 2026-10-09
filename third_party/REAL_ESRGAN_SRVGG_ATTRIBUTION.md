# Anime neural super-resolution provenance

Model: `realesr-animevideov3.pth` (Real-ESRGAN, Xintao Wang)
Source: https://github.com/xinntao/Real-ESRGAN
Release: https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.5.0
Architecture reference: https://github.com/XPixelGroup/BasicSR/blob/master/basicsr/archs/srvgg_arch.py

The model's 4x SRVGGNetCompact neural network is implemented locally as a
minimal equivalent in `tools/sheet_super_resolution.py`, using the official
published anime-video-v3 network parameters. CUDA inference is tile-based.
Asset size is verified against GitHub's release metadata (2,504,012 bytes);
the SHA-256 is measured and recorded locally at download time and checked
on every subsequent model load. **An independent immutable upstream SHA-256
is not available from the release API**, so the size and local receipt must
not be described as remote cryptographic provenance.

The upstream source files are published under BSD 3-Clause:

Copyright (c) 2021, Xintao Wang
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
