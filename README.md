# train-tickets-cli
基于 Python 3.x 的命令行版 12306 火车票查询器

### 安装依赖包
##### Windows
```
pip install requests docopt colorama prettytable
```
##### macOS / Linux
```
pip3 install requests docopt colorama prettytable
```

### 使用方式
##### Windows
```
python src/app.py <from_city> <dest_city> [<date>]
```
##### macOS / Linux
```
python3 src/app.py <from_city> <dest_city> [<date>]
```
### 参数说明
```
from_city - 出发城市，支持拼音输入，例如：成都/chengdu
dest_city - 到达城市，支持拼音输入，例如：重庆/chongqing
date - 乘车日期，格式要求为YYYY-mm-dd，例如：2019-10-24（可选参数，若不传则默认查询当天）
```

### 使用举例
##### Windows
```
python src/app.py 成都 重庆
python src/app.py chengdu chongqing

python src/app.py 成都 重庆 2019-10-24
python src/app.py chengdu chongqing 2019-10-24
```
##### macOS / Linux
```
python3 src/app.py 成都 重庆
python3 src/app.py chengdu chongqing

python3 src/app.py 成都 重庆 2019-10-24
python3 src/app.py chengdu chongqing 2019-10-24
```

### 演示效果
![演示效果图](demo.png?raw=true)