# Local dependency patches

## pywinauto 0.6.9+usbif.1

The upstream `pywinauto 0.6.9` wheel contains an invalid `\;` escape in the
`pywinauto.keyboard` module docstring. Python reports a `SyntaxWarning` whenever
the module is compiled in a fresh environment.

The local `0.6.9+usbif.1` wheel changes that sequence to `\\;`. This preserves
the rendered documentation while making the Python string literal valid. It
also updates `pywinauto.__version__`, the wheel metadata version, the
`.dist-info` directory name, and the wheel `RECORD` manifest.

- Upstream artifact: `pywinauto-0.6.9-py2.py3-none-any.whl`
- Upstream SHA-256: `5924b3072864a1d730c5546bbeb17cf4063ba518b618dbc5e43c18276c7c9356`
- Local artifact: `pywinauto-0.6.9+usbif.1-py2.py3-none-any.whl`
- Local SHA-256: `abc56d8468e467e17ac3e3e13565bbfb49efb32a50510baffc15271b33d24691`
- Source patch: `pywinauto-0.6.9-usbif.1.patch`

To reproduce the wheel, unpack the upstream wheel with `uv run --with wheel
python -m wheel unpack`, apply the source patch, update both version fields and
rename the `.dist-info` directory to `pywinauto-0.6.9+usbif.1.dist-info`, then
repack it with `uv run --with wheel python -m wheel pack`. The pack command
regenerates `RECORD`.
