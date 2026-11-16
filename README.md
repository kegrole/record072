# CSV 流水对账工具

仅使用 Python 标准库实现。输入两份包含 `key`、`amount`、`ts` 列的 CSV，输出确定性的 JSON 对账报告。CSV 列顺序可以不同，程序始终按列名读取。

## 运行

```bash
python -m reconcile.cli --local demo/local.csv --remote demo/remote.csv --out out/report.json
```

命令会生成 JSON，并在 stdout 打印一行摘要，包含对平数、差异数、缺失数、重复数、可疑数和差异金额（分）。也可以使用 `python -m reconcile`，参数相同。

## 金额读法

金额全程使用整数分或 `Decimal` 处理，不使用浮点数。

1. 去掉首尾空白。
2. 删除货币符号和货币代码：`$`、`€`、`£`、`¥`、`￥`、`USD`、`EUR`、`GBP`、`CNY`、`RMB`；代码不区分大小写。
3. 整体被圆括号包住时按负数处理，例如 `(800.00)` 为 `-80000` 分。
4. 否则末尾减号表示负数，例如 `100.00-` 为 `-10000` 分；减号不参与数字解析。
5. 逗号按千分位删除，`1,200.50` 与 `1200.50` 等价。
6. 小数金额乘 100 后采用半分进位（ROUND_HALF_UP）转成整数分，因此 `1.005` 为 `101` 分，不是 `100` 分。
7. 报告中的所有金额字段都以整数分表示，不出现浮点小数金额。

## 时间戳读法

时间统一转换成 UTC 秒级整数。

1. 去掉首尾空白。
2. 纯数字：10 位按 Unix 秒处理；13 位按 Unix 毫秒处理并整除 1000。
3. 非纯数字按 `年-月-日 时:分:秒` 解析，日期和时间之间允许 `T` 或空格。
4. 时区后缀允许 `Z`、`+HH:MM`、`-HH:MM`；没有时区信息时按 UTC 处理。
5. 不依赖旧版 Python 对 `fromisoformat` 的 `Z` 支持。

## 分类规则与优先级

一个键只进入一个分类，按以下优先级判定：

1. **主键重复**：任一侧出现次数不等于 1。只有一侧多次出现也属于重复，不再判为缺失。
2. **缺失**：只在一侧出现。方向分别为 `本地有对端缺` 或 `本地缺对端有`。
3. **金额不一致**：两侧都有且不重复，且 `abs(remote - local) > 1` 分。
4. **可疑**：金额对平，但时间差大于 24 小时，即大于 86400 秒。
5. **对平**：其余键。

容差为 1 分：金额差正好为 `-1`、`0` 或 `1` 都算金额对平。时间差正好 86400 秒不算可疑，边界包含在阈值内。主键先去首尾空白，再做大小写敏感比较。

## 汇总口径

汇总只统计两侧都出现且都不重复的键；只在一侧出现的键和重复键不计入任何金额合计。

- `local_total_cents`：本地原始总账。
- `remote_total_cents`：对端原始总账。
- `raw_diff_cents`：对端原始总账减本地总账。
- `aligned_remote_total_cents`：容差内的配对按本地金额计入；超过容差的配对按对端原始金额计入。
- `total_diff_cents`：对齐后的对端总账减本地总账。
- `sum_of_diffs_cents`：只累加超过容差的配对差异，容差内差异按 0 计。
- `tolerance_cents`：固定为 1。

按上述规则，`total_diff_cents` 始终等于 `sum_of_diffs_cents`。明细中的 `diff_cents` 始终是对端金额减本地金额。

## 报告结构

顶层字段固定为 `matched`、`amount_mismatch`、`missing`、`duplicate`、`suspicious`、`summary`。前五个字段都是数组，并按 `key` 字典序排序。

- `matched`、`amount_mismatch`：`key`、`local_amount_cents`、`remote_amount_cents`、`diff_cents`。
- `missing`：`key`、`side`、`amount_cents`。
- `duplicate`：`key`、`local_count`、`remote_count`。
- `suspicious`：`key`、`local_amount_cents`、`remote_amount_cents`、`time_diff_seconds`。
- `summary`：五个分类计数、六个金额字段和 `tolerance_cents`，共 12 个字段。

所有数组和 JSON 键顺序固定，报告结果与输入行序无关，打乱行序后输出逐字节一致。

## 测试

```bash
python -m unittest test_reconcile -v
```

测试包含演示夹具逐字内容、金额和时间戳边界、分类优先级、汇总对齐、字段结构、行序无关性、变更输入和命令行输出。
