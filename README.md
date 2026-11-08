# crondoc

**解析 crontab，翻译成人话并计算下次执行时间。**

`0 3 * * *` 到底是几点？下个周一还是下个月 1 号？这个表达式是不是永远不会触发？把这些从"脑内翻译"变成一条命令。

[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Zero deps](https://img.shields.io/badge/dependencies-0-brightgreen)](#设计取舍)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![CI](https://github.com/eathink/crondoc/actions/workflows/ci.yml/badge.svg)](https://github.com/eathink/crondoc/actions/workflows/ci.yml)

## 为什么需要它

crontab 的表达式紧凑但难读，而且有几种错误不会被 `cron` 拒绝——它们只是**永远不会执行**，比如 `0 0 30 2 *`（2 月 30 日）。线上任务"配了但没跑"往往要过几天才被发现。

`crondoc` 只做三件事：

1. **翻译** —— 把表达式变成"每周一 09:00"这样的中文
2. **预演** —— 从任意时间点开始，列出接下来 N 次执行时间
3. **体检** —— 未来 5 年内一次都不会触发的表达式，直接标出来并以非 0 退出

只读，不执行命令，不修改 crontab。

## 快速开始

```bash
pipx install git+https://github.com/eathink/crondoc

# 分析一个 crontab 文件
crondoc /etc/crontab

# 单独分析一个表达式
crondoc --expr "0 9 * * MON"
```

输出：

```console
$ crondoc examples/deploy.cron --from 2026-11-09T00:00 --next 3
来源 examples/deploy.cron，起点 2026-11-09 00:00

第 6 行  每天 03:00
  0 3 * * *  /usr/local/bin/backup.sh --full
  下次：2026-11-09 03:00、2026-11-10 03:00、2026-11-11 03:00

第 9 行  每周一 09:00
  0 9 * * MON  /usr/local/bin/cleanup.sh --days 30
  下次：2026-11-09 09:00、2026-11-16 09:00、2026-11-23 09:00

第 12 行  每 15 分钟
  */15 * * * *  /usr/local/bin/sync-config.sh
  下次：2026-11-09 00:15、2026-11-09 00:30、2026-11-09 00:45

第 14 行  每天 00:00
  @daily  /usr/local/bin/rotate.sh
  下次：2026-11-10 00:00、2026-11-11 00:00、2026-11-12 00:00
```

## 用法

```bash
crondoc [SOURCE] [--expr EXPR] [--next N] [--from ISO] [--format text|json]
```

| 参数 | 说明 |
| --- | --- |
| `SOURCE` | crontab 文件路径；`-` 表示从标准输入读取 |
| `-e, --expr` | 直接分析单个表达式，与 `SOURCE` 二选一 |
| `--next N` | 每个任务列出接下来 N 次执行时间，默认 5 |
| `--from ISO` | 计算起点，默认当前时间；例如 `2026-11-09T00:00`，按本地时间处理 |
| `-f, --format` | `text`（默认）或 `json` |
| `--version` | 版本号 |

```bash
# 从标准输入读
crontab -l | crondoc -

# 给 CI / 脚本用
crondoc deploy.cron --format json --next 1
```

## 支持的语法

- 标准 5 字段：`分 时 日 月 周`
- 取值：`*`、单值、列表 `1,15`、范围 `1-5`、步长 `*/15`、组合 `0-30/10`
- 名称：月份 `JAN`–`DEC`，星期 `SUN`–`SAT`
- 星期支持 `0` 和 `7` 都表示周日
- 宏：`@yearly`、`@annually`、`@monthly`、`@weekly`、`@daily`、`@midnight`、`@hourly`
- 日与星期同时受限时，按标准 cron 语义取**或**：`0 0 1 * MON` 表示每月 1 号**或**每周一

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 全部任务正常 |
| 1 | 至少有一个任务在未来 5 年内不会执行 |
| 2 | 表达式 / 文件解析失败 |

适合挂在 CI 或部署前检查里：

```bash
crondoc deploy.cron --next 1 --format json > /dev/null
```

## 已知边界

- **5 年视界**：判断"永不执行"的方式是向后扫描 5 年，没有命中就认为不会执行。这对闰日和月日组合足够，但不是一个数学证明
- **本地时间**：不处理时区与夏令时；跨时区部署请自行换算
- **不支持 `@reboot`**：它没有可计算的时间语义，会明确报错而不是猜
- **不支持秒级字段**：那是 Quartz 的 6/7 字段语法，和标准 crontab 不同

## 设计取舍

- **只读**：分析工具不该有写入权限，也不需要
- **零依赖**：`pipx install` 后即用，适合塞进最小化镜像
- **逐日扫描而不是逐分钟**：先按年/月/日过滤，再只遍历配置过的小时和分钟，保证 `@yearly` 和"永不执行"的表达式也能秒回
- **描述不硬猜**：能明确表达的（每天、每周几、每 N 分钟/小时）用人话，复杂的直接列字段，不生成似是而非的句子

## 开发

```bash
git clone https://github.com/eathink/crondoc
cd crondoc

# 仅用标准库，无需安装依赖
PYTHONPATH=src python3 -m unittest discover -s tests -v

# 本地运行
PYTHONPATH=src python3 -m crondoc examples/deploy.cron --next 3
```

## License

[MIT](LICENSE)
