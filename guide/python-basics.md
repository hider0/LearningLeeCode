# Python 零基础速成：只学刷题用得上的部分

这份文档专为**完全没有编程经验**的学习者准备。目标不是“学会 Python”，而是“学会解答本训练器 41 道题所需的最小 Python 知识”。全文通读加动手练习约需 2～3 小时，之后就可以开始第 1 章。

如果你已经会 Python，直接跳过本文，去[分章学习手册](README.md)。

## 0. 先确认环境

打开终端（Windows 上是 PowerShell 或命令提示符），输入：

```bash
python3 --version    # Windows 上可能是 python --version
```

看到 `Python 3.x.x` 就说明环境可用。再输入 `python3` 回车，进入交互模式（提示符变成 `>>>`），本文所有示例都可以在这里逐行敲进去验证。输入 `exit()` 退出。

**给零基础的建议：不要只看不敲。** 每个例子都亲手输入一次，改一改再运行，出错信息也要读一读——读报错是程序员最重要的基本功。

## 1. 变量与基本类型

变量就是给值起名字，用 `=` 赋值：

```python
age = 18              # 整数 int
price = 9.5           # 小数 float
name = "kimi"         # 字符串 str（引号包裹的一串字符）
passed = True         # 布尔值 bool，只有 True 和 False 两种
nothing = None        # 空值，表示“什么都没有”
```

刷题中最常用的是 **int、str、bool、None** 和下面要讲的容器（list、dict、set）。

## 2. 条件与循环

Python 用**缩进**（行首的 4 个空格）表示代码归属，这是它和其他语言最大的不同：

```python
x = 7
if x > 5:
    print("大于 5")      # 这行属于 if，必须缩进
else:
    print("不大于 5")

for i in range(5):       # i 依次取 0,1,2,3,4
    print(i)

total = 0
while total < 10:        # 条件成立就一直循环
    total += 3           # 等价于 total = total + 3
```

循环里两个常用控制：

- `break`：立刻跳出整个循环；
- `continue`：跳过本次，直接进入下一轮。

## 3. 列表 list：一排带编号的格子

列表是一组有序的元素，下标从 **0** 开始：

```python
nums = [2, 7, 11, 15]
nums[0]        # 2（第一个元素）
nums[-1]       # 15（倒数第一个，负数下标从右往左数）
len(nums)      # 4（长度）
nums[1:3]      # [7, 11]（切片：从下标 1 到 3，含左不含右）
nums.append(9) # 末尾追加，变成 [2, 7, 11, 15, 9]
9 in nums      # True（是否存在，注意：这个操作要逐个检查，较慢）
```

遍历列表的两种写法：

```python
for value in nums:                    # 只要元素本身
    print(value)

for index, value in enumerate(nums):  # 下标和元素都要（刷题高频）
    print(index, value)
```

列表推导式（简洁地批量生成列表，看懂即可）：

```python
squares = [x * x for x in range(5)]   # [0, 1, 4, 9, 16]
```

## 4. 字符串 str：不可变的字符序列

字符串可以像列表一样按下标和切片访问，但**不能修改某个字符**（这叫“不可变”）：

```python
s = "leetcode"
s[0]        # 'l'
s[::-1]     # 'edocteel'（反转字符串的经典切片写法）
s.upper()   # 'LEETCODE'（返回新字符串，s 本身不变）
```

两个高频操作：

```python
", ".join(["a", "b", "c"])   # 'a, b, c'：把列表拼成字符串
sorted("tea")                # ['a', 'e', 't']：排序后得到字符列表
"".join(sorted("tea"))       # 'aet'：两者配合，是字母异位词的关键技巧
```

## 5. 字典 dict 与集合 set：哈希结构的两位主角

**字典**存“键 → 值”的对应关系，查询、插入、删除都极快（平均 O(1)）：

```python
counts = {}
counts["a"] = 1                    # 写入
counts["a"] = counts["a"] + 1      # 读取再写回
counts.get("b", 0)                 # 0：键不存在时返回默认值 0（不会报错）
"a" in counts                      # True：判断键是否存在
```

计数字典是刷题中出现频率最高的模式之一：

```python
counts = {}
for char in "banana":
    counts[char] = counts.get(char, 0) + 1
# 结果：{'b': 1, 'a': 3, 'n': 2}
```

**集合**只存“有哪些元素”，自动去重，查询同样 O(1)：

```python
seen = set()
seen.add(3)
3 in seen          # True
len(set([1, 2, 2, 3]))   # 3：去重后数个数，一行判重
```

**什么时候用谁**：只关心“见没见过”用 `set`；要记录“次数、位置、对应关系”用 `dict`。这是第 1 章的核心直觉。

## 6. 函数 def：可复用的一段逻辑

```python
def add(a, b):
    return a + b      # return 把结果交还给调用者，同时结束函数
```

注意：函数执行到 `return` 就立刻结束，后面的代码不会再运行。没有写 `return` 的函数默认返回 `None`。

## 7. 读懂 `class Solution` 模板

训练器里每道题的代码模板长这样：

```python
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        # 在这里编写你的代码
        pass
```

逐行拆解：

- `class Solution:`：定义一个“类”。你现在只需要知道：**判题器规定答案必须写在这个类的对应方法里**，照抄外壳即可；
- `def twoSum(self, nums, target)`：定义类里的方法。第一个参数 `self` 是约定俗成的写法，**调用时不用管它**，你的逻辑只和后面的参数打交道；
- `nums: list[int]` 和 `-> list[int]`：类型标注，起说明作用（“nums 是整数列表，返回值也是整数列表”），写错也不会影响运行，可以当注释看；
- `pass`：占位符，表示“什么都不做”。你要做的就是删掉它，换成自己的代码，并用 `return` 返回答案。

也就是说，你要写的全部内容，就是方法体里那几行逻辑。

## 8. 常用内置函数速查

| 写法 | 作用 | 例子 |
|---|---|---|
| `len(x)` | 长度 | `len([1,2,3])` → 3 |
| `range(n)` | 生成 0..n-1 | `list(range(3))` → [0,1,2] |
| `enumerate(xs)` | 遍历时带下标 | 见第 3 节 |
| `sorted(xs)` | 排序（返回新列表） | `sorted([3,1,2])` → [1,2,3] |
| `min / max / sum` | 最小/最大/求和 | `max([2,9,4])` → 9 |
| `abs(x)` | 绝对值 | `abs(-5)` → 5 |
| `reversed(xs)` | 反向遍历 | `list(reversed([1,2]))` → [2,1] |

整数除法与取余（二分查找、两数相加都会用到）：

```python
7 // 2    # 3：整除，向下取整
7 % 2     # 1：余数
```

## 9. 新手最常踩的 8 个坑

1. **缩进不一致**：混用 Tab 和空格、或多敲少敲空格，直接报 `IndentationError`。统一用 4 个空格。
2. **用 `/` 当整除**：`7 / 2` 得到 `3.5`（小数），要整数结果请用 `//`。
3. **`[[0] * m] * n` 建二维列表**：内层列表被复制的是“引用”，改一格会改一整列。正确写法：`[[0] * m for _ in range(n)]`。
4. **在列表里频繁 `in`**：`x in list` 要逐个扫描是 O(n)，需要反复查询时改用 `set`。
5. **把可变对象当字典键**：`{}[[]] = 1` 会报错，列表不能作 key，可换成字符串或元组。
6. **字符串当可变对象用**：`s[0] = 'a'` 会报错，字符串不可变，要修改就先转成列表。
7. **忘记 `return`**：函数默认返回 `None`，判题时就会报“期望 X，实际 None”。
8. **下标越界**：`nums[len(nums)]` 不存在，最后一个元素是 `nums[len(nums) - 1]` 即 `nums[-1]`。

## 10. 自测：能独立写出这三段，就可以去第 1 章了

1. 给定列表 `[3, 1, 4, 1, 5]`，用一个 `set` 统计有多少个不同的数；
2. 给定字符串 `"hello"`，用一个 `dict` 统计每个字符出现几次；
3. 写一个函数 `def is_even(n)`，判断整数是否为偶数并返回 `True`/`False`。

写不出来就回到对应小节再敲一遍，写得出来就直接开始：[第 1 章：数组与哈希](01-array-hash.md)。

返回：[分章学习手册](README.md)
