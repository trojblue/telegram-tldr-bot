from pyrogram.types import Message
from urllib.parse import urlsplit


def parse_url_string(orig_text: str) -> dict:
    """
    输入string, 返回url列表和其他文本列表
    :param text: some text https://www.google.com
    :return: {[urls], [other_texts], "original_text"}
    """
    url_list = []
    other_texts = []

    if orig_text is not None:
        try:
            text = orig_text.split()
            for t in text:
                parts = urlsplit(t)
                if parts.scheme and parts.netloc:
                    url = t
                    url_list.append(url)
                    other_texts.append("[url]")
                else:
                    other_texts.append(t)
        except Exception as e:
            print(e)

    return_dict = {
        "urls": url_list,
        "description": other_texts,
        "original": orig_text,
    }

    return return_dict


def retrieve_summary_and_type(url:str):
    """
    从URL中提取summary和type
    :param url:
    :return:
    """
    # Dummy method for retrieving summary and type
    # todo: implement this method
    return "", "unknown"