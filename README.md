# train-tickets-cli
基于 Python 3.7 的命令行版 12306 火车票查询器

### 安装依赖包
```
pip install requests docopt colorama prettytable
或者
pip3 install requests docopt colorama prettytable
```

### 使用方式
```
python train_tickets_cli.py <from_city> <dest_city> [<date>]
或者
python3 train_tickets_cli.py <from_city> <dest_city> [<date>]
```
### 参数解析
```
from_city - 出发城市，例如：成都
dest_city - 到达城市，例如：重庆
date - 乘车日期，例如：2019-10-24，若不传则默认查询当天
```

### 使用举例
```
python train_tickets_cli.py 成都 重庆
python3 train_tickets_cli.py 成都 重庆
或者
python train_tickets_cli.py 成都 重庆 2019-10-24
python3 train_tickets_cli.py 成都 重庆 2019-10-24
```

### 演示效果
![演示效果图](demo.png?raw=true)