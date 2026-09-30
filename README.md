<div align="center">
<h1>Resume</h1>
<img alt="LaTeX" src="https://img.shields.io/static/v1?label=Language&style=flat&message=LaTeX&logo=latex&color=008080&labelColor=393939&logoColor=008080">
<img alt="Shell" src="https://img.shields.io/static/v1?label=Shell&style=flat&message=Bash&logo=gnu+bash&color=4EAA25&labelColor=393939&logoColor=4EAA25">
<img alt="Code+Editor" src="https://img.shields.io/static/v1?label=Code+Editor&style=flat&message=Visual+Studio+Code&logo=visual+studio+code&color=007acc&labelColor=393939&logoColor=007acc">
<br>
<img alt="License" src="https://img.shields.io/github/license/lynkos/resume?style=flat&label=License&labelColor=393939&color=788200&link=https%3A%2F%2Fgithub.com%2Flynkos%resume%2Fblob%2Fmain%2FLICENSE.md">
<img alt="Last Commit" src="https://img.shields.io/github/last-commit/lynkos/resume?style=flat&label=Last+Commit&labelColor=393939&color=be0000">
</div>

## Requirements
- [x] [LaTeX](https://www.latex-project.org/get)
- [x] [Visual Studio Code](https://code.visualstudio.com)

> [!TIP]
> Use [Overleaf](https://www.overleaf.com/) for online LaTeX editing and collaboration

## Installation
1. Enter the directory where you want the repository ([`resume`](https://github.com/lynkos/resume)) to be cloned
  * POSIX
    ```sh
    cd ~/path/to/directory
    ```
  * Windows
    ```sh
    cd C:\Users\user\path\to\directory
    ```
2. Clone the repository ([`resume`](https://github.com/lynkos/resume))
   ```sh
   git clone https://github.com/lynkos/resume.git
   ```

> [!IMPORTANT]
> Make sure `/Library/TeX/texbin`, and a LaTeX installation with `latexmk` is in your `PATH` environment variable

## Tailor Resume
### Quick Start
1. Install with Conda
   ```sh
   conda create -n resume_env python=3.14 pip -y
   conda activate resume_env
   python -m pip install -e ".[dev]"
   ```

2. Create `.env` with API key, model name, email, and phone number:
   ```
   OPENAI_API_KEY="YOUR_API_KEY"
   OPENAI_MODEL="MODEL_NAME"
   EMAIL="EMAIL@DOMAIN.com"
   PHONE_NUMBER="+1 (234) 567--8900"
   ```

3. Configure [`resume.yaml`](resume.yaml) accordingly

### Usage
Generate a resume for a job description in `jobs/archil.txt`
   ```sh
   resume \
     --jd-file jobs/archil.txt \
     --title "Distributed Systems Engineer" \
     --company "Archil"
   ```

Generate a resume for a job description provided via CLI
   ```sh
   resume --jd "Full job description here..." --title "Software Engineer"
   ```

Generate resume for `jobs/pnnl.txt` from existing draft at `examples/pnnl-draft.json` (instead of requesting a new initial draft)
   ```sh
   resume --jd-file jobs/pnnl.txt \
     --title "Early Career Software Engineer" \
     --company "Pacific Northwest National Laboratory" \
     --draft-file examples/pnnl-draft.json \
     --max-backfill-attempts 0 \
     --max-fit-retries 0
   ```

Allow up to 2 pages
   ```sh
   resume --jd-file job.txt --max-pages 2
   ```

Disable both page fitting and backfill
   ```sh
   resume --jd-file job.txt --no-page-limit
   ```

Disable backfill (increasing it allows more candidate trials and LaTeX compilations)
   ```sh
   resume --jd-file job.txt --max-backfill-attempts 0
   ```

| Name                  | Default                   |
| --------------------- | ------------------------- |
| Config                | `resume.yaml`             |
| Template              | `templates/resume.tex.j2` |
| Output Directory      | `Resume/build/`           |
| Max Pages             | `1`                       |
| Max Retries           | `8`                       |
| Max Backfill Attempts | `6`                       |

> [!NOTE]
> Build directory contains:
> - Latest generated `.tex`
> - PDF (when compilation succeeds)
> - LaTeX logs
> - Most recent `draft.json` after any fitting adjustments

### Testing
```sh
PYTHONPATH=src python -m pytest -q tests/test_backfill.py
```

## View Resume in Visual Studio Code
1. Open Visual Studio Code
2. Download [LaTeX Workshop extension](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop)
3. Open the Command Palette
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd>
4. Search and select `Preferences: Open User Settings (JSON)`
5. Add the following lines to `settings.json`:
   ```json
    "latex-workshop.latex.tools": [
       {
         "name": "lualatex",
         "command": "lualatex",
         "args": [
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "%DOC%"
         ],
         "env": {
           "EMAIL": "EMAIL@DOMAIN.com",
           "PHONE_NUMBER": "+1 (234) 567--8900"
         }
       },
       {
         "name": "latexmk",
         "command": "latexmk",
         "args": [
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "-lualatex",
           "-outdir=%OUTDIR%",
           "%DOC%"
         ],
         "env": {
           "EMAIL": "EMAIL@DOMAIN.com",
           "PHONE_NUMBER": "+1 (234) 567--8900"
         }
       },
       {
         "name": "xelatex",
         "command": "xelatex",
         "args": [
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "%DOC%"
         ],
         "env": {}
       },
       {
         "name": "pdflatex",
         "command": "pdflatex",
         "args": [
           "-interaction=nonstopmode",
           "-file-line-error",
           "%DOC%"
         ],
         "env": {}
       },
       {
         "name": "bibtex",
         "command": "bibtex",
         "args": [ "%DOCFILE%" ],
         "env": {}
       }
    ],
    "latex-workshop.latex.recipes": [
       {
         "name": "lualatex",
         "tools": [ "lualatex" ]
       },
       {
         "name": "pdfLaTeX",
         "tools": [ "pdflatex" ]
       },
       {
         "name": "latexmk",
         "tools": [ "latexmk" ]
       },
       {
         "name": "xelatex",
         "tools": [ "xelatex" ]
       },
       {
         "name": "pdflatex ➞ bibtex ➞ pdflatex * 2",
         "tools": [
           "pdflatex",
           "bibtex",
           "pdflatex",
           "pdflatex"
         ]
       },
       {
       "name": "xelatex ➞ bibtex ➞ xelatex * 2",
       "tools": [
         "xelatex",
         "bibtex",
         "xelatex",
         "xelatex"
         ]
       }
    ],
    "latex-workshop.view.pdf.viewer": "tab",
   ```
6.  Save changes to `settings.json` file
    * Mac: <kbd>Command ⌘</kbd> + <kbd>S</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>S</kbd>
7. Open newly cloned `resume` directory in Visual Studio Code
8. Open or create a `.tex` file you want to edit
9. Edit the file as you see fit
10.  Compile the file
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Option ⌥</kbd> + <kbd>B</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>B</kbd>
11.  View the `.pdf` output
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Option ⌥</kbd> + <kbd>V</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>V</kbd>

## References
- [LaTeX Workshop Wiki](https://github.com/James-Yu/LaTeX-Workshop/wiki)
- [How to use LaTeX in VScode as an Overleaf alternative](https://groundwater.usu.edu/blog/2025/Use-Latex-in-VScode)
- [Writing LaTeX Documents In Visual Studio Code With LaTeX Workshop](https://medium.com/@rcpassos/writing-latex-documents-in-visual-studio-code-with-latex-workshop-d9af6a6b2815)
- [A Fast Guide on Writing LaTeX with LaTeX Workshop in VS Code](https://mathjiajia.github.io/vscode-and-latex)