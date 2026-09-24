# RQA 设计级结论稳健化报告（HARDENING REPORT）

分支 `hardening/design-level`，基线 commit `1e7f02f`（原交接状态）。
工作范围：参数化 + 稳健性验证 + 三处局部优化。**未改动**
`experiments/waffle_leakage_sim.py`（逐字节与基线相同，见文末核查），
未重新设计算法，未做 L3 真实二进制实验。

反作弊纪律核查（全程有效）：
- `ATTACK_FIELDS` 白名单保持 `(event, batch_ts, direction, storage_key)`，未增删；
- 真值仍只进入 `load_truth` / `eval_*` / `full_trace_reads` / `match_episodes` /
  `visible_targets` 等评估侧函数；
- 攻击侧函数（`stage_a/b/c/d*`、`batch_features`、`build_incarnations`、
  `permutation_null`、新增 `stage_d_pair_distribution` / `stage_d_calibrate` /
  `_episode_pair_cells`）不读取任何标签或真值；Task 3 校准只消费
  point-burst trace、control trace 与攻击自身的检测结果。
- 全部 stdlib-only；logistic 拟合为手写 Newton/IRLS + 手写 bootstrap。

---

## Task 0 — 参数化 + 修 bug ✅（全部验收通过）

改动：删除 `stage_b_detect_episodes` 中重复的 `detect(features)` 调用
（纯冗余，无行为变化）；9 个硬编码超参提升为 CLI 参数，默认值等于原值：
`--track-span 80`、`--flush-frac 0.08`、`--local-bg 40`、`--min-mass 30`、
`--window 50`、`--gap 3`、`--min-pair-mass 8`、`--max-cell 4`、
`--eviction-tail 15`。`eviction_tail` 在 `stage_d_tracking` 与
`permutation_null` 两处使用同一参数，保持一致。有效参数记录进
`attack_state.json` 新增的 `attack_params` 键。

验收：原版存档 `results/t0_check_orig/` vs 修改版 `results/t0_check/`
（`--quick --seed 7`）：**attack_state.json 除新增键外逐字节相同**；
stage_b/eval/f1 = 0.8718 一致；stage_e boundary 逐值一致。另用非默认
参数组合验证参数确实生效（f1 0.8718→0.8571）。

## Task 1 — 超参敏感性扫描 ✅（验收 (a)(b)(c) 全过）

`experiments/rqa_sensitivity.py`；S1_n8k，seed 7/8/9，每参数独立
{0.5×,1×,2×}（1× 为共享基线），共 81 个运行；trace 按种子缓存，
仅攻击阶段重算。输出 `results/sensitivity/{summary.md, sensitivity.csv}`。

- **结论未翻转：9/9 参数全部 NOT FLIPPED**。判据逐条核验：
  (a) |F1−F1_1x| ≤ 0.15：实测最大偏差 ≈ 0.03（F1 全域 0.87–0.90）；
  (b) 窗口估计移动 ≤ 2 格：全部运行窗口 = 45，仅 max_cell=8 seed8
      为 20（移动 1 格）；
  (c) null 均值 < 攻击 kept-overlap 质量：最差组合 max_cell=2 时
      null=118.7 vs 质量=5271（44× 分离），其余普遍 >1000×。
- (b) 无翻转参数 → 无需单列安全区间（报告中已声明）；如实记录的
  边缘现象：eviction_tail=30 使 kept 质量虚增 +45%（归属放松）、
  max_cell=2 使 null 抬升 2.4→118.7（浓度判据是关键区分器）。
- (c) 3 seed 且逐参数给出 seed 间 F1 标准差（0.000–0.019）。
- 取整说明：gap 0.5×=2（1.5 四舍五入）、eviction_tail 0.5×=8（7.5 取整）。

## Task 2 — 窗口精化（去量化） ✅（验收 (a)(b)(c) 全过，含诚实标注）

改动：`eval_e` 的 boundary 从 5 个硬编码字符串桶改为按**真实 gap 值**
逐对记录 `gap -> [n_pair, hit]`，并输出 pair 级 `(gap, hit, overlap)`
（`boundary_pairs`）；`make_episodes` 经核验本就支持任意 gap 列表
（无需改码）；`--requery-gaps` 默认值保持 20,45,90,200 不变（硬约束 4），
加密网格 {15,25,35,50,65,80,100,130,170,220,300,400} 在精化实验中显式
传入。新脚本 `experiments/rqa_window_refine.py`（手写 Newton/IRLS
logistic MLE + 500× bootstrap）。输出 `results/window_refine/`：
per_gap_recovery.csv、window_fit.csv、law_refit.csv、curve_*.txt、summary.md。

- (a) w 点估计 + 95% CI（不再是量化下界）：
  | 配置 | 旧网格窗口 | 加密网格窗口 | logistic w [95% CI] |
  |---|---|---|---|
  | S1_n8k (3 seed 汇池, 179 对) | 45/45/45 | 65 | **76.3 [69.4, 80.7]**（收敛, k=0.105, 0/500 失败） |
  | S2_n200k (52 对) | 90 | 80 | **108.5 [93.2, 111.6]**（近分离, 区间 (107,110)） |
  | S3_n500k (46 对) | 200 | 220 | **272.0 [224.0, 310.6]**（近分离, 区间 (232,312), 55/500 重采样退化） |
  去量化使窗口上修 +70% / +21% / +36%：旧网格窗口确为系统性低估。
- (b) 定律（window vs (N−C)/f_R，过原点）：legacy 量化窗口复现
  slope=0.731 / R²=0.914（与原 0.75/0.960 一致，5 点）；加密网格
  0.839/0.987；**去量化 w：slope≈1.047 / R²=0.988（仅 3 个尺度点，
  样本弱）**。结论：线性标度形式在去量化后保持，但斜率应从 ~0.75
  修订为 ~1.0（量化偏差压低了原斜率）。
- (c) 曲线形态如实报告：S1 在 gap 25→35 有一次小幅非单调
  （10/12 → 13/13），其余为清晰悬崖（65:1.00 → 80:0.46 → 100:0.00）；
  S2/S3 为近乎完美分离的阶跃（S3: ≤232 全恢复、312 处 0/2），此时
  斜率 k 不可辨识，只报区间，未强行给斜率赋予意义。

## Task 3 — Stage D 关联对精确率 ✅（验收 (a)(b)(c) 全过）

改动：`eval_e` 新增 overlap-pair precision/recall/F1（真值对=交集≥30、
估计正对=matrix>0），分全体与窗口内（窗口固定为基线窗口估计
70/84/68，避免窗口随矩阵移动的循环混淆）；攻击侧新增
`stage_d_pair_distribution` / `stage_d_calibrate`（从 point-burst
控制 trace 的 episode-pair (mass, cell) 分布校准阈值）。
`experiments/rqa_staged_precision.py`，S1 seed 7/8/9。
输出 `results/staged_precision/{summary.md, staged_precision.csv}`。

- (a) 窗口内召回：部署规则 R2（cell≥4 不变，min_pair_mass =
  max(8, q10 of burst 条件分布)）下**每 seed 降幅 0.000** ≤ 0.05 ✓。
- (b) 全体精确率：0.456 → 0.464（每 seed +0.018/+0.000/+0.006，
  无 seed 变差）✓。Pearson(large_overlap)：0.339 → 0.339，
  **未同步改善**（如实报告；小幅 mass 门限上调不改变相关性）。
- (c) 校准数据来源：仅 point-burst trace + 攻击自身在其上的检测
  （服务器可见），eviction_tail 为攻击侧参数；**range 真值未参与
  任何阈值取值**；候选分位数之间的选择由任务的验收约束
  （召回≤0.05、精度提升）驱动，已在 summary 中声明。
- 附带诚实发现：q99 噪声包络规则可把精确率推到 0.845，但窗口内
  召回最多掉 0.630（弱真链接 mass 11–32、cell 4 落在噪声包络内），
  被召回约束否决；S1 上可安全达成的精度增益有限——实质性提升需要
  (mass, cell) 之外的特征，而非阈值调参。

## Task 4 — L3 前置探查（只报告，未编译、未运行）

- **RQA 仓库内：六项资产全部缺失**（waffle_test-main/、build.sh、
  generate_waffle_only_runbook.py、real_waffle_attack_demo.py、
  audit_waffle_source_fidelity.py、claim_evidence_matrix.md；
  run_artifact.py 亦不存在）。**就本仓库而言：L3 资产缺失，L3 阻塞。**
- 同机存在**另一项目**的兄弟工作区 `/home/selom/Waffle-attack-artifact`
  （交接文档所述"父 artifact 仓库"），其中六项资产齐全
  （C++ proxy 源码 Cache.cpp/FrequencySmoother.cpp/waffle_proxy.cpp、
  server、benchmark、thrift/proxy.thrift、build.sh 等）。本任务未从该
  工作区搬运、编译或运行任何资产。
- 若未来在该兄弟工作区启动 L3，build 依赖清单（据 build.sh/CMakeLists
  与源码结构）：cmake ≥3.5（本机 3.27.9 ✓）、C++ 工具链（g++ ✓）、
  redis-server（✓）、Thrift 运行时/编译器（本机 PATH 未见 thrift
  可执行文件 —— **缺口**）。已知语义风险（交接文档 §7.1）：真实
  Cache.cpp 命中不刷新 LRU 位，会先冲击 Stage A 的 flush 通道。
- 结论：**L3 就绪度 = 阻塞（本仓库无资产；外部工作区资产在位但
  thrift 缺失且未经本仓库验证）。**

---

## 逐项验收对照表

| Task | 验收项 | 结果 | 证据 |
|---|---|---|---|
| 0 | 修重复 detect() | ✅ | commit 2e5f161；删除一行 |
| 0 | 9 参数 CLI 化、默认不变、eviction_tail 两处同参 | ✅ | attack_params 键；git diff |
| 0 | quick seed7 输出与原版逐值一致 | ✅ | attack_state.json 除新键外逐字节相同 |
| 1 | (a) 标注结论是否翻转 | ✅ | 9/9 NOT FLIPPED（判据写在 summary） |
| 1 | (b) 翻转参数安全区间 | ✅（无需） | 无翻转；边缘现象已列 |
| 1 | (c) ≥3 seed + seed 间标准差 | ✅ | 3 seed；逐参数 sd 0.000–0.019 |
| 2 | (a) w 点估计 + 95% CI | ✅ | 76.3[69.4,80.7] / 108.5[93.2,111.6] / 272[224,310.6] |
| 2 | (b) 新旧差异 + 定律斜率复算 | ✅ | +70%/+21%/+36%；0.75→~1.05（R² 0.988, 3 点） |
| 2 | (c) 非清晰 sigmoid 如实报告 | ✅ | S1 一处小反转；S2/S3 近分离只报区间 |
| 3 | (a) 窗口内召回降幅 ≤0.05 | ✅ | R2 每 seed 0.000 |
| 3 | (b) 全体精确率提升 + 报告 Pearson | ✅ | +0.008（无 seed 变差）；Pearson 不变（已报） |
| 3 | (c) 校准只用 control/point-burst | ✅ | summary 纪律声明；代码路径可查 |
| 4 | 只列清单不执行 | ✅ | 见上；未编译未运行 |

## 残余局限（诚实清单）

1. 敏感性扫描仅在 S1_n8k（任务指定的最小配置）上做；S2–S3/M1–M2
   未扫（计算量原因），跨规模稳健性仍由原 14 运行矩阵背书。
2. 定律去量化复算只有 3 个尺度点（S1/S2/S3，各 1 个 w），斜率 ~1.05
   的置信区间未定；S4 与 M1/M2 未纳入。
3. Task 3 的精度增益小（+0.008）；S1 上 (mass, cell) 特征的可达上限
   已被探明，更大增益需新特征。
4. 全部结论仍为 design-level（模拟器级）；真实负载、第二系统、
   L3 均未做（见 Task 4）。
5. claim_evidence_matrix.md 不在本仓库（属父 artifact 仓库），本报告
   承担其声明-证据对照职能。

## 一句话结论

**设计级结论达到档位1（稳健、非手调 artifact）：是** —— 依据：9 个
攻击超参在 ±2× 三档、3 种子下无一翻转结论（F1 变化 ≤0.03、窗口
稳定、null 分离 ≥44×），窗口定律在去量化后给出带 95% CI 的 w
（76.3/108.5/272）且线性标度形式保持（斜率修订为 ~1.0），Stage-D
精确率已量化并可用纯服务器可见数据校准小幅改善且不伤召回；但该
结论的边界是：模拟器级、S1 为中心的稳健性、合成负载，且 L3 资产
在本仓库缺失（L3 阻塞）。
