# 公开测试网实验：run-20260915-public

本轮采用 Conflux eSpace Testnet（71）及隔离合约
`0x49Fda55aEFfa835375290217Cd69E9bFFf17039b`。原件通过 GitHub
公共仓库托管，没有使用本地 EVM、IPFS 或生产身份。

## 为什么这样设计

合法登记/更新是阳性对照；同一已绑定身份上的 Relayer 伪签、旧请求重放、
URI 调包检验代付方是否仍无权修改。L 单独承担换钥、旧钥拒绝、新钥更新、
撤销和撤销后拒绝的生命周期测试，避免污染目录中 A--D 的有效对照。

目录层构造 A--D 有效，E 的签署 URI 返回 404，F 返回版本被改的内容，
H 返回错误标识，G/L 撤销。完整视图 ABCD 与删减视图 ACD 使用相同的
确认快照和范围；两份视图的全部条目都应通过单条验证，但后者应漏列 B。
这些异常是人工控制的机制用例，不是自然用户的故障发生率。

E 的原件仍归档于 originals/，仅签署的取件路径不可取，不声称全网丢失。
F/H 的异常文件从初次发布即为受控不匹配响应，没有修改固定 commit。
IPFS 讨论仅为存储备选，本轮没有 CID 或 pinning 的实测结果。

## 公开版本与安全边界

- 仓库：https://github.com/PakHeiPoon/agent-profile-thesis-evidence
- 原件 commit：`34c6ccdfd758e61bbae4bd968ece03ad8932c82d`
- URI 示例：https://raw.githubusercontent.com/PakHeiPoon/agent-profile-thesis-evidence/34c6ccdfd758e61bbae4bd968ece03ad8932c82d/run-20260915-public/cards/A.json
- 本地 `public/` 在公共仓库中命名为 `cards/`；`cards-manifest.json` 中的
  文件路径按本地准备目录记录，内容摘要一致。
- 端侧密钥随机生成，仅在准备进程内使用；不写出私钥。既有 Relayer
  私钥仅在远端读取，未复制到工作区或公共仓库。
- 每笔费用上限 0.02 测试 CFX，全轮上限 0.3 测试 CFX；不发主网交易。
- 发送前写入交易哈希 journal；超时或断言异常时停止，不自动重复广播。

## 复核方法

`../../testnet_mechanisms.py` 生成授权并提交真实交易；
`../../testnet_audit.py` 是独立的只读实验审计器，并不是生产索引器升级。
审计器从部署块开始按 `(blockNumber, transactionIndex, logIndex)` 重放事件，
对照固定结束块的直接合约状态，再通过 HTTPS 取回原件。至少等待结束块后
12 个块，并在审计前后核对块哈希。两个 RPC 不代表两个独立运营商，
也不把后继块数量当作不可逆最终性证明。

公开比较视图是固定快照的静态分页夹具，不是生产服务实施恶意分裂视图的
观测。比较会实际下载全部分页、核对范围、快照、总数和重复条目。

## 状态

本轮执行与独立审计已完成。

- 实际交易 19 笔：14 成功、5 拒绝；拒绝后完整记录均不变。
- 10 个端侧地址前后余额、交易计数均为零。Relayer nonce 连续为 12--30。
- 区块范围：262638705--262638930；结束块哈希
  `0x879dea9a35d812e18094b53935907b6ab5329cd66540af136a6a8152a18919eb`。
- 审计开始时已观察到 22 个后继块（最低要求 12）；收据均经备用 RPC 复核。
- 14 条事件重建 9 个身份状态，全部与同块合约查询一致。
- 分类：有效 4、不可取 1、摘要不符 1、标识不符 1、撤销 2。
- 完整视图差集为空；删减视图差集恰为 B，尽管其中 3 条记录都能逐条验证。
- 公开视图 commit：`c242d992a5016c6fe05a534532b2c994c9654a4c`；均实际下载两页。
- 实际费用：0.11071962 测试 CFX，不含部署费用；每笔均与余额变化一致。
  执行 Gas 共 4740612，计费 Gas 共 5535981，Gas price 20 Gwei。
  [Conflux 退款规则](https://doc.confluxnetwork.org/docs/espace/build/evm-compatibility/)
  要求区分 gasUsed 与 gasCharged，不能直接用前者当实际扣费。

原始证据见 `evidence/run-results.json`、逐笔 submitted/receipt/result 文件、
`audit/chain-audit.json`、`audit/transactions-rechecked.json` 和
`audit/view-comparison.json`。结果不代表形式化安全证明、长期可用性、
完整生产服务端到端验证或性能优势。旧在线服务和原合约未修改。
