# Third-Party Notices

AgentWisper depends on third-party software. Each component remains under its
own license; the AgentWisper MIT License does not replace those terms.

## Runtime Python distributions

| Component | Declared license | Upstream |
| --- | --- | --- |
| NumPy | BSD-3-Clause and bundled component licenses | https://github.com/numpy/numpy |
| pynput | LGPL-3.0 | https://github.com/moses-palmer/pynput |
| six | MIT | https://github.com/benjaminp/six |
| Pyperclip | BSD | https://github.com/asweigart/pyperclip |
| pywebview | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| Bottle | MIT | https://github.com/bottlepy/bottle |
| proxy-tools | BSD-style | https://github.com/jtushman/proxy_tools |
| pythonnet | MIT | https://github.com/pythonnet/pythonnet |
| clr-loader | MIT | https://github.com/pythonnet/clr-loader |
| CFFI | MIT-0 | https://github.com/python-cffi/cffi |
| typing-extensions | PSF-2.0 | https://github.com/python/typing_extensions |
| sherpa-onnx and sherpa-onnx-core | Apache-2.0 | https://github.com/k2-fsa/sherpa-onnx |
| python-sounddevice | MIT | https://github.com/spatialaudio/python-sounddevice |
| pycparser | BSD-3-Clause | https://github.com/eliben/pycparser |

The exact dependency versions used by a source checkout are recorded in
`uv.lock`. Packaged builds collect the license and copying files provided by
installed runtime distributions. `third_party/proxy-tools/LICENSE.txt` is kept
in this repository because that distribution does not install its upstream
license file.

Development-only tools are not part of the AgentWisper runtime distribution
and retain their respective upstream licenses.

