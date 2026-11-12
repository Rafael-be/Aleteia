"""Conservative zero-model gate; ambiguity passes to semantic extraction."""
import re
import unicodedata

MESSAGE = 'Envie uma afirmação ou pergunta factual para eu verificar.'


def is_noise(text: str) -> bool:
    text = unicodedata.normalize('NFKC', text).strip()
    if not text:
        return True
    if not any(c.isalnum() for c in text):
        # Mathematical questions may contain only symbols.
        return not bool(re.search(r'[=+×÷√∫π]', text))
    compact = re.sub(r'\s+', '', text).casefold()
    if re.fullmatch(r'(.)\1{7,}', compact):
        return True
    return compact in {'asdfghjkl', 'asdfgh', 'qwertyuiop', 'qwerty', 'zxcvbnm', 'lkjhgfdsa'}
