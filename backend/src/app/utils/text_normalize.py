"""日本語テキスト正規化ユーティリティ。"""

import re
import unicodedata


def normalize_jp(text: str) -> str:
    """NFKC正規化 + カタカナ→ひらがな + 記号除去。"""
    # NFKC: 全角英数→半角、半角カナ→全角カナ等
    text = unicodedata.normalize("NFKC", text)
    # カタカナ→ひらがな (ァ-ヶ → ぁ-ゖ)
    result = []
    for ch in text:
        cp = ord(ch)
        if 0x30A1 <= cp <= 0x30F6:
            result.append(chr(cp - 0x60))  # 0x30A1 - 0x3041 = 0x60
        else:
            result.append(ch)
    text = "".join(result)
    # 記号除去: 中黒・コロン・空白等
    text = re.sub(r"[・：:\s\u3000]", "", text)
    return text


def contains_normalized(haystack: str, needle: str) -> bool:
    """正規化後の部分一致判定。needle が2文字未満なら False（過短一致防止）。"""
    if len(needle) < 2:
        return False
    return normalize_jp(needle) in normalize_jp(haystack)
