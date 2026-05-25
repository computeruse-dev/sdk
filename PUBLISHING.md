# Publishing the `computeruse` package

The `sdk/` directory builds a publish-ready `computeruse==0.0.1` preview package. As of the last commit:

```
dist/computeruse-0.0.1-py3-none-any.whl  ← validated, twine check PASSED
dist/computeruse-0.0.1.tar.gz            ← validated, twine check PASSED
```

## One-time setup (you, ~5 minutes)

1. **Create a PyPI account** at <https://pypi.org/account/register/>. Enable 2FA (required for new packages).
2. **Generate an API token** at <https://pypi.org/manage/account/token/>:
   - Token name: `computeruse-publish` (or whatever)
   - Scope: "Entire account" (you can re-scope after the first upload)
   - **Copy the token immediately** — PyPI shows it once. Format: `pypi-AgEIcHl…`
3. (Optional but recommended) Add the token to `~/.pypirc` so you don't paste it every time:
   ```ini
   [pypi]
     username = __token__
     password = pypi-AgEIcHl…
   ```

## Publish (~60 seconds)

```bash
cd /Users/buryhuang/git/cloudbrowser.live/sdk

# Build fresh artifacts (in the existing venv)
rm -rf dist build
.venv/bin/python -m build

# Upload to PyPI
.venv/bin/twine upload dist/*
# (will prompt for username + password if ~/.pypirc not set;
#  username is __token__, password is the pypi-Ag… token)
```

Within ~30 seconds, anyone in the world can run:

```bash
pip install computeruse
```

…and get the preview stub, which prints the waitlist banner and raises `PreviewError` on `Sandbox.claude()`. Mission accomplished — the homepage command resolves to something legitimate.

After publishing, re-scope the PyPI token to "project: computeruse" only (more secure than entire-account).

## Verify after publish

```bash
# Anywhere, with a clean Python:
pip install computeruse
python -c "from computeruse import Sandbox; Sandbox.claude()"
# Expect: PreviewError with the waitlist message
```

Check the listing at <https://pypi.org/project/computeruse/>.

## Push the source to GitHub

The SDK lives in this repo at `sdk/` for now. To split it into its own repo at `github.com/computeruse-dev/sdk`:

```bash
# From this repo's root
cd /Users/buryhuang/git/cloudbrowser.live

# Create a fresh repo for the SDK
mkdir -p /tmp/computeruse-sdk-init
cp -r sdk/* sdk/.gitignore /tmp/computeruse-sdk-init/
cd /tmp/computeruse-sdk-init
git init
git add .
git commit -m "Initial preview release · 0.0.1"
git branch -M main
git remote add origin https://github.com/computeruse-dev/sdk.git
git push -u origin main
```

(Or copy the dir to wherever you keep your repos and `gh repo create computeruse-dev/sdk --source=. --public --push`.)

## Subsequent releases

Bump the version in `pyproject.toml` (PyPI requires monotonically increasing versions), rebuild, upload:

```bash
# Edit pyproject.toml: version = "0.0.2"
rm -rf dist build
.venv/bin/python -m build
.venv/bin/twine upload dist/*
```

PyPI does **not** allow re-uploading the same version. If a build is broken, bump (e.g. `0.0.1.post1`) and re-upload.

## npm equivalent (later)

The TypeScript SDK isn't built yet. When it is, the publish flow is:

```bash
npm login                              # one-time
npm publish --access public            # from the package dir
```

Reserve `@computeruse/sdk` and `computeruse` on npm the same way once the JS package exists.
