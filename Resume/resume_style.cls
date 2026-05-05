% Resume Style in LaTeX

% Author: Kiran Brahmatewari
% Website: https://github.com/lynkos
% License: MIT
%------------------------

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume_style}[2026/05/01 Custom Resume Class]

%----------------------------------------------------------------------------------
%                                   Base class
%----------------------------------------------------------------------------------
\LoadClass[letterpaper,11pt]{article}

%----------------------------------------------------------------------------------
%                                   Packages
%----------------------------------------------------------------------------------
\RequirePackage{latexsym}
\RequirePackage[empty]{fullpage}
\RequirePackage{titlesec}
\RequirePackage{marvosym}
\RequirePackage{multicol}
\RequirePackage[usenames,dvipsnames]{color}
\RequirePackage{verbatim}
\RequirePackage{enumitem}
\RequirePackage[pdftex]{hyperref}
\RequirePackage{fancyhdr}
\RequirePackage{tikz}
\RequirePackage{fontawesome}

\usetikzlibrary{positioning, calc}

%----------------------------------------------------------------------------------
%                                   Page styling
%----------------------------------------------------------------------------------
\pagestyle{fancy}
\fancyhf{} % clear all header and footer fields
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}
\setlength{\footskip}{4.1pt}

%----------------------------------------------------------------------------------
%                                   Magin adjustments
%----------------------------------------------------------------------------------
\addtolength{\oddsidemargin}{-0.475in}
\addtolength{\evensidemargin}{-0.375in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

%----------------------------------------------------------------------------------
%                                   Sections formatting
%----------------------------------------------------------------------------------
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

%----------------------------------------------------------------------------------
%                                   Custom commands
%----------------------------------------------------------------------------------
\newcommand{\listItem}[2]{
  \item\small{
    \textbf{#1}{#2}
  }\vspace{-2pt}
}

% Adjusts spacing between items in "Skills" section
\newcommand{\skillsListItem}[2]{
  \item\small{
    \textbf{#1}{#2}
  }\vspace{-5.5pt}
}

\newcommand{\subheading}[4]{
  \vspace{-1pt}\item
    \begin{tabular*}{0.982\textwidth}{l@{\extracolsep{\fill}}r}
      \textbf{#1} & {\small#2}\\
      \textit{\small#3} & \textit{\small#4}\\
    \end{tabular*}\vspace{-5pt}
}

\newcommand{\subItem}[2]{\listItem{#1}{#2}\vspace{-4pt}}

% Changes bullet points to circles instead of dashes
\renewcommand{\labelitemii}{$\circ$}

\newcommand{\subheadingListStart}{\begin{itemize}[leftmargin=*,label={}]} % ,itemsep=0pt for no spacing between items
\newcommand{\subheadingListEnd}{\end{itemize}}
\newcommand{\itemListStart}{\begin{itemize}}
\newcommand{\itemListEnd}{\end{itemize}\vspace{-5pt}}