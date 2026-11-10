"""Exceções da camada de Domínio."""


class DomainError(Exception):
    """Exceção base para todos os erros de negócio do domínio."""


class SongNotFoundError(DomainError):
    """Lançada quando uma música não é encontrada no catálogo ou armazenamento."""


class LyricsNotFoundError(DomainError):
    """Lançada quando a letra de uma música não é encontrada no armazenamento."""


class InvalidAudioFormatError(DomainError):
    """Lançada quando um formato de arquivo de áudio não é suportado ou é inválido."""


class InvalidScoreError(DomainError):
    """Lançada quando a pontuação está fora do intervalo permitido (0 a 100)."""


class InvalidLyricsTimeError(DomainError):
    """Lançada quando o tempo de início ou fim de uma linha de letra é inválido."""


class AudioDownloadError(DomainError):
    """Lançada quando ocorre uma falha ao baixar ou extrair áudio."""


class AudioSeparationError(DomainError):
    """Lançada quando ocorre uma falha na separação de faixas por IA."""


class PitchExtractionError(DomainError):
    """Lançada quando ocorre uma falha na extração de pitch/afinação."""


class SongNotReadyError(DomainError):
    """Lançada quando uma música é acessada antes de estar pronta para uso."""


class InvalidPitchPointError(DomainError):
    """Lançada quando os parâmetros de um ponto de afinação são inválidos."""


class InvalidScorerConfigError(DomainError):
    """Lançada quando os parâmetros de configuração do avaliador são inválidos."""


class InvalidStoragePathError(DomainError):
    """Lançada quando um caminho ou arquivo de armazenamento é inválido."""


class AudioAnalysisError(DomainError):
    """Lançada quando ocorre uma falha durante análise de sinal de áudio."""


class ForcedAlignmentError(DomainError):
    """Lançada quando ocorre uma falha no alinhamento forçado de letra/áudio."""
