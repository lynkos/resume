<div align="center">
<h1>Resume</h1>
<img alt="Python" src="https://img.shields.io/static/v1?label=Language&style=flat&message=Python+3.14.7&logo=python&color=c7a228&labelColor=393939&logoColor=4f97d1">
<img alt="LaTeX" src="https://img.shields.io/static/v1?label=Language&style=flat&message=LaTeX&logo=latex&color=008080&labelColor=393939&logoColor=008080">
<img alt="Jinja" src="https://img.shields.io/static/v1?label=Language&style=flat&message=Jinja&logo=jinja&color=7E0C1B&labelColor=393939&logoColor=7E0C1B">
<img alt="Shell" src="https://img.shields.io/static/v1?label=Shell&style=flat&message=Bash&logo=gnu+bash&color=4EAA25&labelColor=393939&logoColor=4EAA25">
<img alt="Conda" src="https://img.shields.io/static/v1?label=Tool&style=flat&message=Conda&logo=anaconda&color=44A833&labelColor=393939&logoColor=44A833">
<img alt="Code+Editor" src="https://img.shields.io/static/v1?label=Code+Editor&style=flat&message=Visual+Studio+Code&logo=visual+studio+code&color=007acc&labelColor=393939&logoColor=007acc">
<br>
<img alt="License" src="https://img.shields.io/github/license/lynkos/resume?style=flat&label=License&labelColor=393939&color=788200&link=https%3A%2F%2Fgithub.com%2Flynkos%resume%2Fblob%2Fmain%2FLICENSE.md">
<img alt="Last Commit" src="https://img.shields.io/github/last-commit/lynkos/resume?style=flat&label=Last+Commit&labelColor=393939&color=be0000">
<br>
LLM-assisted, deterministic LaTeX resume tailoring.
</div>

## Requirements
- [x] [LaTeX](https://www.latex-project.org/get) (including [`latexmk`](https://www.cantab.net/users/johncollins/latexmk))
- [x] [Conda](https://www.anaconda.com/download) (preferred) or [Python](https://www.python.org/downloads)
- [x] [Visual Studio Code](https://code.visualstudio.com)

## Installation
Clone and enter the repository
  ```sh
  git clone https://github.com/lynkos/resume.git && cd resume
  ```

> [!IMPORTANT]
> Make sure a LaTeX installation with `latexmk` (e.g. `/Library/TeX/texbin`) is in your `PATH` environment variable

## Tailor Resume
<div align="center">
  <img src="tailoring_algorithm.svg" alt="Resume tailoring algorithm">
</div>

### Quick Start
1. Create new Conda environment `resume_env`
   ```sh
   conda create -n resume_env python=3.14 pip -y
   ```

2. Activate environment
   ```sh
   conda activate resume_env
   ```

3. For testing, install optional dependencies
   ```sh
   python -m pip install -e ".[dev]"
   ```

4. Create `.env` file with these values and configure accordingly
   ```
   OPENAI_API_KEY="YOUR_API_KEY"
   OPENAI_MODEL="MODEL_NAME"
   EMAIL="EMAIL@DOMAIN.com"
   PHONE_NUMBER="+1 (234) 567--8900"
   ```

5. If needed, edit [`resume.yaml`](resume.yaml)

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

Generate resume for `job.txt` with `draft.json` (instead of requesting new initial draft)
   ```sh
   resume \
     --jd-file job.txt \
     --title "Software Engineer" \
     --company "Some National Laboratory" \
     --draft-file draft.json \
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

<details open>
  <summary><strong>Command Line Arguments</strong></summary>
   <table align="center" style="width: 100%; text-align: center; display: block; max-width: -moz-fit-content; max-width: fit-content; overflow-x: auto;">
     <thead>
       <tr>
         <th align="center">Option</th>
         <th align="center">Type</th>
         <th align="center">Description</th>
         <th align="center">Default</th>
       </tr>
     </thead>
     <tbody>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--jd-file &lt;path&gt;</code></td>
         <td align="center"><code>Path | None</code></td>
         <td align="center">Path to a text file containing the job description</td>
         <td align="center"><code>None</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--jd &lt;job description&gt;</code></td>
         <td align="center"><code>str | None</code></td>
         <td align="center">Literal job-description text</td>
         <td align="center"><code>None</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--title &lt;title&gt;</code></td>
         <td align="center"><code>str | None</code></td>
         <td align="center">Optional job title</td>
         <td align="center"><code>None</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--company &lt;company&gt;</code></td>
         <td align="center"><code>str | None</code></td>
         <td align="center">Optional company name</td>
         <td align="center"><code>None</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--config &lt;path&gt;</code></td>
         <td align="center"><code>Path</code></td>
         <td align="center">Resume YAML source of truth</td>
         <td align="center"><code>"resume.yaml"</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--template &lt;path&gt;</code></td>
         <td align="center"><code>Path</code></td>
         <td align="center">Jinja LaTeX template</td>
         <td align="center"><code>"resume.tex.j2"</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--output-dir &lt;path&gt;</code></td>
         <td align="center"><code>Path</code></td>
         <td align="center">Directory for generated TeX/PDF/debug files</td>
         <td align="center"><code>"Resume/build"</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--output-name &lt;name&gt;</code></td>
         <td align="center"><code>str</code></td>
         <td align="center">Base filename for generated TeX/PDF</td>
         <td align="center"><code>"resume"</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--max-pages &lt;int&gt;</code></td>
         <td align="center"><code>int</code></td>
         <td align="center">Maximum allowed PDF page count; minimum: <code>1</code></td>
         <td align="center"><code>1</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--no-page-limit</code></td>
         <td align="center"><code>bool</code></td>
         <td align="center">Disable the PDF page-count requirement</td>
         <td align="center"><code>False</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--max-fit-retries &lt;int&gt;</code></td>
         <td align="center"><code>int</code></td>
         <td align="center">Maximum number of one-change fitting retries; minimum: <code>0</code></td>
         <td align="center"><code>8</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--max-backfill-attempts &lt;int&gt;</code></td>
         <td align="center"><code>int</code></td>
         <td align="center">Maximum additions tested after fitting; minimum: <code>0</code>, which disables backfilling</td>
         <td align="center"><code>6</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--draft-file &lt;path&gt;</code></td>
         <td align="center"><code>Path | None</code></td>
         <td align="center">Start from a saved draft instead of generating a new selection; must be an existing file</td>
         <td align="center"><code>None</code></td>
       </tr>
       <tr>
         <td align="center" style="white-space: nowrap;"><code>--model &lt;model&gt;</code></td>
         <td align="center"><code>str | None</code></td>
         <td align="center">OpenAI model; otherwise uses <code>OPENAI_MODEL</code> from <code>.env</code></td>
         <td align="center"><code>None</code></td>
       </tr>
     </tbody>
   </table>
</details>

### Testing
```sh
PYTHONPATH=src python -m pytest -q tests/test_backfill.py
```

## View Resume
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
         "name": "latexmk",
         "command": "latexmk",
         "args": [
           "-lualatex",
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "-outdir=%OUTDIR%",
           "%DOC%"
         ],
         "env": {
           "EMAIL": "EMAIL@DOMAIN.com",
           "PHONE_NUMBER": "+1 (234) 567--8900"
         }
       },
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
         "name": "bibtex",
         "tools": [ "bibtex" ]
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