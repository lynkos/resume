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
3. Make sure `/Library/TeX/texbin` is in your `PATH` environment variable
4. Open Visual Studio Code
5. Download [LaTeX Workshop extension](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop)
6. Open the Command Palette
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd>
7. Search and select `Preferences: Open User Settings (JSON)`
8. Add the following lines to `settings.json`:
   ```json
    "latex-workshop.latex.tools": [
       {
         "name": "latexmk",
         "command": "latexmk",
         "args": [
           "-synctex=1",
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "-outdir=%OUTDIR%",
           "%DOC%"
         ],
         "env": {}
       },
       {
         "name": "xelatex",
         "command": "xelatex",
         "args": [
           "-synctex=1",
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
           "-synctex=1",
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
       },
       {
         "name": "lualatex",
         "command": "lualatex",
         "args": [
           "-synctex=1",
           "-interaction=nonstopmode",
           "-file-line-error",
           "-pdf",
           "%DOC%"
         ],
         "env": {}
       }
    ],
    "latex-workshop.latex.recipes": [
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
         "name": "lualatex",
         "tools": [ "lualatex" ]
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
9. Save changes to `settings.json` file
    * Mac: <kbd>Command ⌘</kbd> + <kbd>S</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>S</kbd>

## Usage
1. Open newly cloned `resume` directory in Visual Studio Code
2. Open or create a `.tex` file you want to edit
3. Edit the file as you see fit
4. Compile the file
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Option ⌥</kbd> + <kbd>B</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>B</kbd>
5. View the `.pdf` output
    * Mac: <kbd>Command ⌘</kbd> + <kbd>Option ⌥</kbd> + <kbd>V</kbd>
    * Windows: <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>V</kbd>

## Repository Structure
<details open>
<summary>Click to expand/hide</summary>
<pre>
.
├── Previous Resumes/
│   └── ...
├── Resume/
│   ├── common/
│   │   ├── experience/
│   │   │   ├── acyd.tex
│   │   │   ├── fiu_stem.tex
│   │   │   └── oci.tex
│   │   ├── projects/
│   │   │   ├── algae-ai.tex
│   │   │   ├── grovers-algo.tex
│   │   │   ├── iphone-apps.tex
│   │   │   ├── jekyll-chirpy.tex
│   │   │   ├── mac-windows.tex
│   │   │   ├── personal-blog.tex
│   │   │   └── personal-website.tex
│   │   ├── education.tex
│   │   ├── experience.tex
│   │   ├── heading.tex
│   │   ├── priv.tex
│   │   ├── projects.tex
│   │   └── skills.tex
│   ├── Kiran_Brahmatewari_Resume_Short.tex
│   ├── Kiran_Brahmatewari_Resume.tex
│   └── resume_style.cls
├── .gitignore
├── LICENSE.md
└── README.md
</pre>
</details>

## References
- [LaTeX Workshop Wiki](https://github.com/James-Yu/LaTeX-Workshop/wiki)
- [How to use LaTeX in VScode as an Overleaf alternative](https://groundwater.usu.edu/blog/2025/Use-Latex-in-VScode)
- [Writing LaTeX Documents In Visual Studio Code With LaTeX Workshop](https://medium.com/@rcpassos/writing-latex-documents-in-visual-studio-code-with-latex-workshop-d9af6a6b2815)
- [A Fast Guide on Writing LaTeX with LaTeX Workshop in VS Code](https://mathjiajia.github.io/vscode-and-latex)