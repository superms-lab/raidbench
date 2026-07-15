# RaidBench 公开网站中文审阅稿

> 仅供站长内部审阅。这个文件不放进公开网站，不给海外玩家看到。公开站点继续保持英文。

## 总体判断

RaidBench 现在是一个英文玩家工具和攻略站，定位不是“卖游戏道具”、不是“代练”、不是“外挂/漏洞教程”，而是帮助玩家在行动前做判断：

- Rust：计算 raid 成本、硫磺消耗、维护成本，并提供基础攻略。
- Palworld：围绕基地选址、自动化、Boss 准备、繁殖目标、资源路线做清单式攻略。
- Path of Exile 2：围绕版本敏感的 build 检查、防御缺口、Boss 准备、掉落过滤器、货币 farming、物品价值判断做轻量攻略。

现在对外展示的核心策略是：先用免费 SEO 页面和工具吸引玩家，验证搜索需求与玩家问题；等 PayPal/Payoneer/其他收款方案、客服邮箱、交付流程、退款流程都稳定后，再开放付费产品入口。

## 已发现并处理的公开风险

- 法律页面顶部导航残留了 `Premium` 入口。这个入口已经移除，避免用户误以为现在可以购买。
- 付费产品草案页曾经可通过猜 URL 打开。现在公开内容已经替换为安全跳转页，并加了 `_redirects`；真实付费草案只应留在 `operations/` 或未来受保护后台。
- `PayPal`、`Stripe`、`Paddle`、`Lemon Squeezy`、`Creem` 等字样只保留在隐私政策和退款政策中，语义是“未来启用付费产品时可能由第三方处理支付”，不是当前销售承诺。

## 建议保留的合规语句

这些英文提示虽然看起来保守，但应该保留：

- `unofficial` / `not affiliated with or endorsed by ...`：说明网站是非官方粉丝工具，不隶属于游戏发行商。
- `Verify after major patches` / `Refresh after major updates`：说明攻略和数字会随版本变化，需要更新。
- `No checkout required`：说明当前免费，不要求付款。
- `Do not rely on bug behavior` / `Do not sell exploit-dependent methods`：说明不卖漏洞打法，也不鼓励利用 bug。

## 首页中文理解

首页标题：`Find the expensive mistake before you commit the run.`

中文意思：在你真正投入 raid 前，先找出最贵的错误。也就是玩家在 Rust 里准备炸墙、炸门、花硫磺之前，先用计算器估算成本，避免拿错爆炸物、低估材料、选错目标。

首页当前展示：

- Raid Cost Calculator：计算 Rust raid 目标需要多少 rockets、C4、satchels、explosive ammo。
- Upkeep Estimator：估算基地每周需要多少木头、石头、金属碎片、HQM。
- Fast SEO guide starters：一批 Rust 免费攻略入口，比如门墙成本、solo raid、硫磺路线、TC upkeep。

这部分可以公开。它的语气像工具站，不像夸大收益或诱导付费。

## Rust 攻略中文理解

Rust 页面主要解决这些问题：

- 某类墙或门需要多少 raid 成本。
- 最便宜打法是什么，但同时提醒“最便宜不一定最好”。
- solo/duo 玩家如何分工、准备物资、设置撤退和止损条件。
- 基地为什么 decay、TC 维护怎么算、wipe day 先升级什么。
- raid 后怎么判断是否值得、硫磺是否亏本。

公开风险低。注意不要把内容写成真实世界暴力、赌博、黑产或外挂承诺；目前内容是游戏内规划，表达是正常的。

## Palworld 页面中文理解

Palworld Lab 标题：`Fix the bottleneck before rebuilding the whole base.`

中文意思：不要一发现基地不顺就重建整座基地，先找到真正卡住生产的瓶颈。

当前公开页面包括：

- Beginner progression checklist：新手推进清单，避免资源分散。
- Base location checklist：基地选址清单，看资源、交通、地形、扩展空间。
- Base automation scorecard：基地自动化评分，找工作适性、搬运、存储、队列瓶颈。
- Boss prep checklist：Boss 准备清单。
- Breeding goal checklist：繁殖目标清单，先定义想要的 Pal、被动词条、用途。
- Resource route planner：资源路线规划，把缺材料的问题变成路线和基地分工。

公开风险低。页面里有一句 `This lab avoids exploit-dependent routes`，意思是“不做依赖漏洞的路线”，应该保留。

## POE2 页面中文理解

POE2 Lab 标题：`Check the guide before spending your currency.`

中文意思：在花游戏内 currency 之前，先检查攻略是否可靠。这里的 `currency` 是 Path of Exile 2 游戏里的通货，不是现实货币。

当前公开页面包括：

- Starter build checklist：跟 build 前先检查版本、职业、技能、装备要求。
- Outdated build guide checklist：判断攻略是否过期。
- Endgame defense checklist：进入后期前检查防御缺口。
- Boss prep checklist：Boss 战前准备。
- Loot filter setup checklist：掉落过滤器设置。
- Currency farming checklist：游戏内通货 farming 清单。
- Item value triage：判断物品要留、查价、卖掉还是忽略。
- Endgame route scorecard：比较刷图、Boss、farm、推进路线是否适合自己的 build。
- Build planner roadmap：未来做完整 planner 前的路线图。

公开风险中低。这里最容易误解的是 `currency`，但在 POE2 玩家语境里它是游戏内常用词，可以保留。

## 法律页面中文理解

隐私政策、服务条款、退款政策目前的核心意思：

- 网站会收集基础使用数据，如页面浏览、计算器交互、指南点击、浏览器类型、大致地区、来源。
- 如果未来启用付费或早鸟表单，可能收集邮箱、玩家类型、订单记录。
- 支付信息未来由 PayPal/Stripe/Paddle/Lemon Squeezy/Creem 等第三方处理，本站不保存原始银行卡号。
- 目前真实 checkout 未启用，退款政策是为未来数字产品准备。
- 数字产品未来一般按 14 天内申请退款处理，重复付款、未交付、打不开、描述严重不符等情况可退款。
- 不承诺攻略一定带来某个游戏结果，因为游戏会更新、服务器规则不同、玩家执行不同。

这些内容适合保留。等真实支付上线前，需要再按最终收款商、公司主体、税务身份、目标市场重新审一次。

## 目前不应公开展示的内容

以下内容可以保留在内部文档或后台，不应在公开站直接展示：

- 付费产品草案、价格、点数包、套餐名称。
- 尚未接入的 PayPal/Payoneer/Stripe 购买按钮。
- “保证收益”“保证过 Boss”“保证 farming 利润”等承诺。
- 依赖 bug、漏洞、外挂、脚本或违反游戏服务条款的打法。
- 未经验证的论坛评论自动回复模板，尤其是带链接的推广语。

## 推荐对外口径

可以公开：

> RaidBench is an unofficial player planning lab. Use calculators and checklists to avoid costly in-game mistakes before committing resources.

中文理解：

> RaidBench 是一个非官方玩家规划工具站，帮助玩家在投入游戏资源前，用计算器和清单避免昂贵错误。

不建议公开：

> Pay to win faster / guaranteed profit / bug route / exploit method / official solution.

中文理解：

> 不要说“付费就一定赢”“保证收益”“漏洞路线”“官方方案”。

## 下一步中文后台建议

可以做一版只给你看的中文后台，但不要做成无保护的公开静态页面。推荐路线：

1. 短期：继续用 `operations/` 内部中文 Markdown 和 CSV 做站长审阅。
2. 中期：用 Cloudflare Access 保护 `/owner` 或 `/admin`，只有你登录后能看中文后台。
3. 后期：后台显示每篇攻略的英文公开稿、中文摘要、风险标签、更新时间、来源链接、是否可发布、是否需要人工复核。
