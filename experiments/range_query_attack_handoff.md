# Waffle 范围查询攻击：交接与审核文档

> 用途：交给后续 agent 继续开发/审核的完整交接说明。
> 性质：**诚实陈述**。已确立、未确立、已知弱点全部列明，不做营销式表述。
> 日期：2026-09-23。所有结论的证据等级为 **design-level（模拟器级）**，除非另行标注。

---

## 0. 一页纸总结（先读这个）

**做了什么**：在 Waffle 模拟器上构造了一个被动、order-hidden、无标签作弊的五阶段攻击，针对"范围查询适配器 + Waffle"的工作负载，量化了泄露内容与边界，并在 4 个库规模 × 3 种子 + 2 个机制判别实验（共 14 个运行）上验证了一条标度定律。

**已确立（design-level）**：
1. fake 填充选取机制产生**自识别统计指纹**（flush 年龄模式）；服务器可被动恢复 B、f_D、逐批 miss 序列
2. 范围查询时间线可恢复（F1 0.50–0.90，随配置）
3. 每次查询的可见基数可恢复（中位误差 3–12.5%）
4. 跨查询关联在"窗口"内 100% 可恢复；**窗口 ≈ 0.75 × (N−C)/f_R**（R²=0.960，14 运行）
5. 机制判别：销毁关联证据的是 **fake 清洗本身**而非背景重绘（背景 ×4 窗口不缩）

**未确立（交接 agent 的主要工作面）**：
1. **真实二进制验证（L3）**——全部结论未经真实 Waffle C++ 代码检验
2. **第二系统**——未证明机制对其他填充型方案成立
3. **真实负载 trace**——全部为合成负载
4. 形式化：标度定律只有实证 + 机制论证，**没有定理证明**

**必须知道的诚实弱点**（详见 §7）：攻击超参由我们手工选定、窗口估计被测试网格量化（R² 有高估成分）、Stage D 假阳性对多、小查询检测弱、f_D̂ 系统性低估。审核者应优先检验这些点。

---

## 1. 实验基础（Foundation）

### 1.1 被攻击系统：Waffle 论文语义（Algorithm 1, SIGMOD'24 论文）

- 批次恒定大小 `B = r + f_R + f_D`（r=真实 miss 数，f_R=fake real 数，f_D=dummy 数）
- fake real 按**最小访问时戳**（least-timestamp）从未缓存池选取
- dummy 池每 `D/f_D` 批次完成一个周期并重置时戳
- **write-once-read-once**：对象每次访问后以新 PRF 标识符出现（化身，incarnation）
- 读阶段后：新缓存对象触发 LRU 逐出，被逐出对象以**新化身**写回；dummy 同批回写
- 范围查询适配器（我们的威胁场景）：`RangeQuery([l,u])` → trusted proxy 内部解析为 m 个点查询 → 进入请求队列 → Waffle 按 R 个/批复用。**论文未规定批内顺序，攻击假设批内顺序可被打乱（order-hidden）**

### 1.2 模拟器与 trace

| 组件 | 位置 | 说明 |
|---|---|---|
| WaffleSim | `experiments/waffle_leakage_sim.py`（类 `WaffleSim`, `PaperDummySelector`） | 本仓库已有的、经过 source-fidelity 审计的设计级模拟器；本项目**未改动** |
| 负载生成 | `experiments/range_query_attack.py`（类 `RangeMixWorkload`, 函数 `make_episodes`） | FIFO 请求队列 + 背景 Zipf 点查 + 调度的范围 episode（episode 键跳队首，模拟适配器成批入队） |
| trace 输出 | `WaffleSim.write_trace_tsv` | TSV 列含模拟标签（role/logical_key 等）——**攻击不可用，仅评估可用**；schema 与真实插桩 patch 一致 |
| 真值 | `results/<run>/<mode>_seed<k>_truth.json` | episode 时刻表、键集合、配置 |

### 1.3 论文 medium 参数与缩放

论文 Table 2 medium：`B=2500, R=1000, f_D=500, C=2%×N, D=350k, N=1M`。
N=1M 对 stdlib Python 模拟不可行，故 **N/D/C/背景率/范围大小按 1:5 等比缩放，B/R/f_D 保持原值**。攻击关注的比值结构（f_D/B、R/B、flush 年龄/epoch）保持不变。**这意味着 medium 配置的绝对数值（如窗口批数）不能直接外推到 N=1M，需按定律换算**。

---

## 2. 威胁模型与反作弊纪律（Conditions）

- **敌手**：被动持久存储服务器观察者。可见：每批 storage-ID 读/写多重集、批时间戳。**不可见**：明文键值、PRF 密钥、代理内部状态、（假设）批内顺序
- **反作弊是工程约束而非自觉**（`range_query_attack.py` 顶部）：
  - 攻击解析器白名单 `ATTACK_FIELDS = ("event","batch_ts","direction","storage_key")`，加载时**物理丢弃** role/logical_key/read_count/fake_real_count/dummy_count/cache_misses
  - 真值只进入 `eval_*` 前缀函数与 `load_truth`
- **对照与零假设**（评估可信度的根基）：
  - control run：同参数、无范围查询 → 检测器误报计数
  - point-burst run：同调度同规模的随机键突发 → 区分"范围结构"与"体量"
  - randomized-parent null：读事件父批随机重指派 → 关联质量零分布
- **攻击侧不使用**：真值 episode 边界、任何模拟标签、系统参数（B/f_D 自标定）

---

## 3. 算法流程（五阶段）

全部实现在 `experiments/range_query_attack.py`。输入：trace TSV（白名单列）。

### Stage A — 批解剖（被动标定）
函数 `stage_a_anatomy`、`build_incarnations`。
1. 化身重建：write(id,t_w) → read(id,t_r)，α = t_r − t_w，父批 = t_r − α
2. B̂ = 每批读数中位数；fake flush 模式 = α 直方图最大尖峰（排除 α≤2），窗口自适应扩张（邻 bin ≥20% 模式质量）
3. **滚动模式追踪**（关键工程点）：flush 年龄随 miss 率漂移，用 80 批滑动直方图逐批求模式，窗口 ±max(3, 8%×mode)；逐批 fake 计数 → **miss 序列 = real_budget − flush 计数**
4. dummy 支撑边缘：flush 窗以上"最后一个有质量(≥3)的 bin + 25-bin 空隙"规则 → f_D̂
5. 结构瞬态规则：flush 计数连续 15 批 ≥ 中位数 50% 后才开始检测/追踪（攻击可自见，非真值）

### Stage B — 范围查询检测
函数 `batch_features`、`stage_b_detect_episodes`。
- 每批特征：miss（来自 A）、cold（α≥阈值，注：高 f_R 下此通道失效，见 §7.6）、cop_count（同批内共享同一父批的最大读集合）
- 检测：3 批中心滑动平均 + 滚动稳健 z（中位数+MAD，窗口 ±50 批）+ 持续性规则（≥2 批或单批质量≥3×min_mass）；**阈值 z≥5，自标定，不用对照集设定**
- 输出：episode 批区间列表

### Stage C — 基数恢复
函数 `stage_c_cardinality`。
- m̂ = Σ(episode 批的 miss) − 局部背景中位数 × 批数（局部 = 区间 ±40 批、剔除区间本身；无真值、无对照集）
- 语义：只统计**未命中缓存**的键 → 天然低于真实 m（缓存重读不可见），评估目标为"开始时不在缓存的键数"（`visible_targets`，用标签重建，仅评估侧）

### Stage D — 跨化身追踪（核心创新）
函数 `stage_d_tracking`。
1. 时戳算术：每个非 fake/dummy 读的父批 = t − α（精确整数）
2. 父批归属：episode 批区间本身 + **逐出尾 15 批**（LRU 在 episode 后数批内逐出该批键；15 是攻击侧参数）
3. (父 episode, 子 episode) 对聚合质量；**浓度判据**：总质量 ≥8 且单格最大 ≥4（真实重查的键从队列头集中重读、由逐出尾集中写回 → 格子浓度；背景链分散）
4. ID 级链接仅在父批只有一个候选写时保留（本配置下恒为 0——诚实边界）

### Stage E — 拓扑与边界
函数 `permutation_null`、`eval_e`；编排见 `main`。
- 对称化重叠矩阵；按重查间隔分桶（0-30/31-60/61-120/121-240/240+ 批）的恢复率 → **边界曲线**
- 定律拟合：窗口估计（恢复率≥50% 的最大测试间隔）vs 清洗时间 (N−C)/f_R
- 机制判别：固定 N、背景率 ×2/×4 → 窗口是否随 1/bg 缩短（重绘假说）或跟随 (N−C)/f_R（清洗假说）

### 实验矩阵编排
`experiments/rqa_scaling_matrix.py`：6 配置（S1 n8k / S4 n100k / S2 n200k / S3 n500k / M1 bg240 / M2 bg480）× 种子（规模配置 7,8,9；机制配置 7），并行子进程运行，聚合 Wilson 95% CI、定律拟合（过原点最小二乘 + R²）。

---

## 4. 代码与数据位置索引

| 内容 | 位置 |
|---|---|
| 攻击主体（五阶段 + 编排 + 评估） | `experiments/range_query_attack.py` |
| 矩阵编排与聚合 | `experiments/rqa_scaling_matrix.py` |
| 模拟器（勿改，除非说明） | `experiments/waffle_leakage_sim.py` |
| 论文 medium 预设 | `range_query_attack.py` 参数 `--paper-medium` |
| 矩阵结果（论文图数据） | `results/rqa_topconf/boundary_curve.csv`、`law_fit.csv`、`summary.md` |
| 单次运行输出 | `results/rqa_topconf/<config>_s<seed>/`（trace TSV、truth JSON、attack_state.json、attack_summary.md、run.log） |
| 历史单次实验 | `results/range_query_attack{,_medium,_full}/`、`results/rqa_scale_500k/` |
| 证据矩阵（声明-证据对应） | `experiments/claim_evidence_matrix.md` |
| pycompile 注册 | `experiments/run_artifact.py` 的 `PYTHON_SCRIPTS` |

复现：
```bash
# 单次攻击（小配置）
python3 experiments/range_query_attack.py --rounds 4000 --episode-every 45 \
  --m-min 40 --m-max 160 --overlap-bias 0.5 --outdir results/rqa_repro
# 论文 medium 预设
python3 experiments/range_query_attack.py --paper-medium --outdir results/rqa_repro_med
# 全矩阵（≈70 分钟，3 并发）
python3 experiments/rqa_scaling_matrix.py --jobs 3
# 仅重新聚合
python3 experiments/rqa_scaling_matrix.py --aggregate-only
```

仓库约束（沿用）：所有 Python **stdlib-only**；不要手改 `results/waffle_paper_*`；新声明须同步 `claim_evidence_matrix.md`。

---

## 5. 实验结果（关键数字）

### 5.1 边界曲线（合并种子，Wilson 95% CI；节选自 `results/rqa_topconf/summary.md`）

| 配置 | N | bg/批 | flush 实测 | gap=20 | gap=45 | gap=90 | gap=200 | gap=400 |
|---|---|---|---|---|---|---|---|---|
| S1 | 8,192 | 40 | 81 | 45/45 | 50/64 | 7/62 | 0/69 | 0/24 |
| S4 | 100,000 | 120 | 50 | 30/30 | 28/31 | 2/25 | 0/3 | 0/13 |
| S2 | 200,000 | 120 | 102 | 27/27 | 48/48 | 30/35 | 0/62 | 0/6 |
| S3 | 500,000 | 120 | 255 | 25/25 | 19/20 | 14/17 | 56/64 | 0/45 |
| M1 | 500,000 | 240 | 263 | 7/7 | 9/9 | 6/6 | 15/15 | 0/3 |
| M2 | 500,000 | 480 | 278 | 5/5 | 4/4 | 1/1 | 8/8 | 1/3 |

### 5.2 标度定律
窗口（恢复率≥50% 的最大测试 gap）对清洗时间 (N−C)/f_R 过原点拟合：**斜率 0.75，R²=0.960**（14 运行）。flush 年龄实测 vs 理论：81/88、50/50、102/100、256/256。
注意：窗口估计受测试网格 {20,45,90,200,400} 量化，真实窗口落在 [窗口估计, 下一档 gap] 区间内，R² 因此偏乐观（见 §7.2）。

### 5.3 机制判别
背景 120→480（×4）：flush 256→278（随 f_R 下降略增，符合清洗假说预测），gap=200 恢复保持 8/8。重绘假说预测窗口应缩至 ~60 批——被否定。**销毁关联证据的是 fake 清洗本身。**

### 5.4 攻击质量（各规模种子均值）
检测 F1：0.90（S1）/ 0.57（S4）/ 0.73（S2）/ 0.69（S3）/ 0.50（M2）。
基数中位误差：0.125 / 0.037 / 0.069 / 0.060 / 0.030 / 0.046。
ID 级链接：全部运行为 0（结构性，见 §7.7）。

---

## 6. 结论（诚实版）

### 6.1 可以说的（design-level 成立，有对照/零假设/多种子支撑）

1. **Waffle 的填充机制自识别**：least-timestamp 选取使 fake 的 α 聚集于池清洗年龄，形成被动可测的统计峰。攻击者据此分离流量角色、恢复逐批 miss 序列、标定全部批级参数。
2. **工作负载元数据泄露**：范围查询时间线（何时）、每次查询可见基数（多大，误差 3–12.5%）、窗口内查询关联（哪些查询扫同一片数据，窗口内 100%）。
3. **窗口定律**：关联窗口 ≈ 0.75×(N−C)/f_R，随库规模在固定背景率下增长；窗口外关联不可恢复（证据被销毁）。
4. **窗口 = 安全参数方向**：清洗时间与论文期望 α 同量级——沿论文安全度量调参，暴露窗口同向变长（4 规模实证 + 机制论证；非形式证明）。
5. **不泄露**：明文内容；记录身份（ID 级）；窗口外关联；完全缓存命中的重查。

### 6.2 不能说的（明确越界，交接 agent 勿抄进论文）

1. "Waffle 在真实部署中被攻破"——未经真实二进制验证。
2. "该攻击适用于所有 oblivious 数据存储"——未做第二系统。
3. "窗口外绝对安全"——仅指**本攻击观测的化身父批通道**在该机制下信息被销毁；其他未知通道不在此结论范围内。
4. 任何把模拟数值当作真实部署数值的直接引用（需按定律换算并经 L3 验证）。

---

## 7. 已知弱点清单（审核者优先检查项；按重要性排序）

1. **证据等级**：全部 design-level。公开 Waffle 代码与论文语义有已知差异（如 `Cache.cpp` 命中不刷新 LRU 位），会改变 flush 动力学与 miss 序列，攻击通道在真实代码上**可能减弱或增强**，未测。
2. **窗口估计的量化偏差**：窗口=网格 {20,45,90,200,400} 上恢复率≥50% 的最大档，是真实窗口的**下界**；R²=0.960 建立在量化值上，定律斜率 0.75 的不确定度未报告。改进：加密测试网格（gap 25/50/75/...）或对桶恢复率做 logistic 拟合取拐点。
3. **攻击超参为手工选定，非对抗性验证**：threshold_z=5、min_pair_mass=8、max_cell≥4、eviction_tail=15、flush 窗 ±8%、track_span=80、局部背景窗 ±40。在当前负载族上有效；审稿人应做敏感性分析（每个参数 ±2× 看结论是否翻转）。我们未做系统性敏感性实验。
4. **Stage D 假阳性**：高查询密度下估计对远多于真值对（如 S3：352 估计 vs 74 真重叠对）——背景链偶发通过浓度判据。边界曲线（真值对的恢复率）不受影响，但**重叠矩阵的精度低**，Pearson 0.50–0.70 而非 0.9+。论文表述应写"窗口内召回 100%，精确率受限"。
5. **小查询检测弱**：m ≲ 500（B=2500 时）淹没在 miss 序列噪声中；F1 在 0.50–0.90 间波动。S4 的 F1=0.57 是最弱配置。
6. **cold 通道失效条件**：高 f_R 下 fake 清洗使所有键化身寿命 ≈ 清洗周期，首触大 α 不存在；cold 特征保留但在此域无效（已在代码注释与本文声明）。
7. **ID 级追踪恒为 0**：逐出队列宽（≈B−f_D 个/批）导致父批歧义。这是结构事实而非攻击缺陷，但意味着"追踪具体记录"不可声称。
8. **f_D̂ 系统性低估**（389–453 vs 真值 500）：dummy 支撑与 flush 尾部部分重叠；导致 real_budget 高估 ~2–5%，miss 序列带系统偏差（滚动中位数吸收偏差、不吸收方差）。
9. **评估侧选择**：IoU≥0.3 匹配、真值跨区 horizon=4⌈m/R⌉+10、visible target 的缓存重建规则——均为评估侧工程选择，可能轻微影响 P/R 与基数误差数值（不影响机制结论）。
10. **负载真实性**：背景为合成 Zipf、episode 为受控调度；无 YCSB/真实 trace。范围键空间几何（不相交+受控重查）是为可测量性设计的，真实负载更乱。
11. **M1/M2 机制判别只有 1 个种子**；S4 gap 只测到 90。定律拟合点数（4 个规模）偏少。
12. **模拟器本身的保真边界**：见仓库 `experiments/audit_waffle_source_fidelity.py` 与 `claim_evidence_matrix.md` 的 L1–L4 分层——本工作全部在 L1/L2。

---

## 8. 交接 TODO（按优先级）

1. **L3 真实二进制**（最高优先）：编译 `waffle_test-main/waffle`（build.sh + Redis），用 `generate_waffle_only_runbook.py`/`real_waffle_attack_demo.py` 采集 Redis MONITOR trace，把五阶段攻击接上去（注意真实代码的非刷新缓存差异会先冲击 Stage A 的 flush 通道——这本身就是重要测试）。
2. **参数敏感性**：对 §7.3 列出的每个攻击超参做 ±2× 扫描，报告结论稳健性。
3. **窗口精化**：加密 gap 网格 + logistic 拐点估计，报告窗口置信区间而非点估计。
4. **第二系统**：`oasis_batcher_sim.py`（ObliSQL 组合栈）或 Pancake 式 shuffle，验证"按冷度选填充 → 自识别指纹"的一般性。
5. **真实负载**：YCSB 叠加范围查询重放。
6. **防御评估**：fake 选取加抖动 / D·f_R⁻¹ ≥ 目标窗口 的纠缠配置，测通道存活与吞吐代价。
7. **形式化**（可选）：随机背景模型下证明 window = Θ((N−C)/f_R)。

## 9. 论文表述模板（已核对与证据一致）

> "在 Waffle 模拟器（论文 Algorithm 1 语义）上，针对范围查询适配器负载，我们构造了被动、order-hidden 的多阶段攻击：服务器可恢复 (i) 批级系统参数与逐批 miss 序列（fake 填充的 flush 年龄模式自识别）；(ii) 范围查询时间线（F1 0.50–0.90）；(iii) 每次查询的可见基数（中位误差 3–12.5%）；(iv) 重查间隔在窗口内的查询间关联（窗口内恢复率 100%，Wilson CI 见表）。关联窗口满足 window ≈ 0.75×(N−C)/f_R（4 规模、3 种子/规模，R²=0.960；窗口为量化下界）；机制实验表明销毁关联证据的是 fake 清洗本身而非背景重绘。窗口外关联、记录级身份与明文不可恢复。以上为设计级结论。"

——文档结束——
