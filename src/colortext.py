#!/usr/bin/env python3
"""对命令行显示彩色文字的方法做一些简单封装，在主程序中以模块的方式来调用"""

from colorama import Fore, Style


def light_red(content=''):
    return _fore_color(color=Fore.RED, content=content)


def light_green(content=''):
    return _fore_color(color=Fore.GREEN, content=content)


def light_blue(content=''):
    return _fore_color(color=Fore.BLUE, content=content)


def light_yellow(content=''):
    return _fore_color(color=Fore.YELLOW, content=content)


def _fore_color(color=Fore.WHITE, content=''):
    """将命令行中的内容 content 显示为指定的颜色 color"""
    content = content if isinstance(content, str) else str(content)
    return color + content + Style.RESET_ALL
