#!/usr/bin/env python3
'''
对命令行显示彩色文字的方法做一个简单封装，在主程序中以模块的方式来调用，提升代码整体的可读性和可维护性
'''

from colorama import Fore, Style

def color(color = Fore.WHITE, content = ''):
    '''
    对内容 content 以 color 颜色显示在命令行
    '''
    content = content if isinstance(content, str) else str(content)
    return color + content + Style.RESET_ALL

def light_red(content = ''):
    return color(color = Fore.LIGHTRED_EX, content = content)

def light_green(content = ''):
    return color(color = Fore.LIGHTGREEN_EX, content = content)

def light_blue(content = ''):
    return color(color = Fore.LIGHTBLUE_EX, content = content)

def light_yellow(content = ''):
    return color(color = Fore.LIGHTYELLOW_EX, content = content)
