class ResumeBuildError(RuntimeError):
    pass


class ResumeCompileError(ResumeBuildError):
    pass


class ResumeOverflowError(ResumeBuildError):
    pass


class ResumeLLMError(RuntimeError):
    pass