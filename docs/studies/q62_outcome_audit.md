# Q6.2 真实行为后果与提示干预审计

评价类型：EXPLORATORY_POST_HOC。仅使用既有真实证据；新增真实请求0。
原预注册拒绝/完成主结论保持NO_CLEAR_DIFFERENCE；本轮不能事后宣布B胜利。
行为适当性UNRESOLVED；人工审核尚未完成；长期真人相似性NOT_TESTED。

## 分层与单位

L1是事实约束，L2是客观状态净变化，L3需要独立偏好、任务与人工标准。
hunger_relief=before−after（正值净降低，负值不裁剪）；energy_change=after−before；
money_delta=after−before；净支出/收入不代表错误/优劣；minutes_elapsed=after−before。
饥饿/精力均为合成milli参数（范围0..1000），金钱为cents，非真实生理测量。
模拟分钟、API延迟秒、整轮墙钟秒分别记录，不相加；缺失为UNKNOWN/null，不补0。
库存是净持有变化，不能据净零断言未购买/未进食；媒体/游戏/工作未触发时NOT_EXERCISED。

## 单次决策与宏活动粒度

TRAVEL完成表示已到目的地；MEAL可以包括旅行、购买、进食，粒度不同。
去餐厅是可能的准备动作而不是自动失败；MEAL不是人类标准答案。
不观测也不推断A下一步会吃饭或永不吃饭；本轮未运行假想续步。

## 全部分配单元与24对

每对保留同scenario/repeat的两侧；两个超时侧无有效提案，后果未知。
主要B−A描述来自完整配对；两个重复是相同冻结状态，不是独立真人样本。

|配对/状态/家族/重复|A提案/执行|B提案/执行|A/B饥饿前→后|A状态后果|B状态后果|A/B位置|A/B库存、媒体、游戏、工作|B−A|完整/后端/缺失|支持与边界|
|---|---|---|---|---|---|---|---|---|---|---|
|p001/s10/MEAL_PAYMENT/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_bread/DECISION_ACCEPTED/完成=True|800→815 / 800→495|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_bread': 1}/{'food_bread': 1}|净饥饿降低(milli):320; 精力变化(milli):-30; 金钱变化(cents):-1200; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p002/s03/POST_MEAL_NEED/2|MEAL/food_meal/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|815→245 / 815→245|净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|restaurant→restaurant / restaurant→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):0; 精力变化(milli):0; 金钱变化(cents):0; 模拟分钟:0; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p003/s07/ACTIVITY_LOCATION/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|600→615 / 600→45|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p004/s10/MEAL_PAYMENT/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_bread/DECISION_ACCEPTED/完成=True|800→815 / 800→495|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_bread': 1}/{'food_bread': 1}|净饥饿降低(milli):320; 精力变化(milli):-30; 金钱变化(cents):-1200; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p005/s08/ACTIVITY_LOCATION/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|615→630 / 615→60|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|office→restaurant / office→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p006/s09/MEAL_PAYMENT/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p007/s11/MEAL_SUPPLY/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p008/s01/OWNERSHIP/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p009/s11/MEAL_SUPPLY/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p010/s12/MEAL_SUPPLY/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_bread/DECISION_ACCEPTED/完成=True|800→815 / 800→495|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_bread': 1}/{'food_bread': 1}|净饥饿降低(milli):320; 精力变化(milli):-30; 金钱变化(cents):-1200; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p011/s09/MEAL_PAYMENT/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p012/s02/OWNERSHIP/2|MEAL/food_meal/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→245 / 800→245|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):0; 精力变化(milli):0; 金钱变化(cents):0; 模拟分钟:0; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p013/s06/MEDIA_PROGRESS/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|1000→1000 / 1000→400|净饥饿降低(milli)=0; 精力变化(milli)=0; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=600; 精力变化(milli)=0; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0, '10': 0, '100': 0, '101': 0, '102': 0, '103': 0, '104': 0, '105': 0, '106': 0, '107': 0, '108': 0, '109': 0, '11': 0, '110': 0, '111': 0, '112': 0, '113': 0, '114': 0, '115': 0, '116': 0, '117': 0, '118': 0, '119': 0, '12': 0, '120': 0, '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '2': 0, '20': 0, '21': 0, '22': 0, '23': 0, '24': 0, '25': 0, '26': 0, '27': 0, '28': 0, '29': 0, '3': 0, '30': 0, '31': 0, '32': 0, '33': 0, '34': 0, '35': 0, '36': 0, '37': 0, '38': 0, '39': 0, '4': 0, '40': 0, '41': 0, '42': 0, '43': 0, '44': 0, '45': 0, '46': 0, '47': 0, '48': 0, '49': 0, '5': 0, '50': 0, '51': 0, '52': 0, '53': 0, '54': 0, '55': 0, '56': 0, '57': 0, '58': 0, '59': 0, '6': 0, '60': 0, '61': 0, '62': 0, '63': 0, '64': 0, '65': 0, '66': 0, '67': 0, '68': 0, '69': 0, '7': 0, '70': 0, '71': 0, '72': 0, '73': 0, '74': 0, '75': 0, '76': 0, '77': 0, '78': 0, '79': 0, '8': 0, '80': 0, '81': 0, '82': 0, '83': 0, '84': 0, '85': 0, '86': 0, '87': 0, '88': 0, '89': 0, '9': 0, '90': 0, '91': 0, '92': 0, '93': 0, '94': 0, '95': 0, '96': 0, '97': 0, '98': 0, '99': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0, '10': 0, '100': 0, '101': 0, '102': 0, '103': 0, '104': 0, '105': 0, '106': 0, '107': 0, '108': 0, '109': 0, '11': 0, '110': 0, '111': 0, '112': 0, '113': 0, '114': 0, '115': 0, '116': 0, '117': 0, '118': 0, '119': 0, '12': 0, '120': 0, '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '2': 0, '20': 0, '21': 0, '22': 0, '23': 0, '24': 0, '25': 0, '26': 0, '27': 0, '28': 0, '29': 0, '3': 0, '30': 0, '31': 0, '32': 0, '33': 0, '34': 0, '35': 0, '36': 0, '37': 0, '38': 0, '39': 0, '4': 0, '40': 0, '41': 0, '42': 0, '43': 0, '44': 0, '45': 0, '46': 0, '47': 0, '48': 0, '49': 0, '5': 0, '50': 0, '51': 0, '52': 0, '53': 0, '54': 0, '55': 0, '56': 0, '57': 0, '58': 0, '59': 0, '6': 0, '60': 0, '61': 0, '62': 0, '63': 0, '64': 0, '65': 0, '66': 0, '67': 0, '68': 0, '69': 0, '7': 0, '70': 0, '71': 0, '72': 0, '73': 0, '74': 0, '75': 0, '76': 0, '77': 0, '78': 0, '79': 0, '8': 0, '80': 0, '81': 0, '82': 0, '83': 0, '84': 0, '85': 0, '86': 0, '87': 0, '88': 0, '89': 0, '9': 0, '90': 0, '91': 0, '92': 0, '93': 0, '94': 0, '95': 0, '96': 0, '97': 0, '98': 0, '99': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):600; 精力变化(milli):0; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p014/s06/MEDIA_PROGRESS/1|UNKNOWN/PROVIDER_TIMEOUT/完成=UNKNOWN|MEAL/food_meal/DECISION_ACCEPTED/完成=True|1000→UNKNOWN / 1000→400|净饥饿降低(milli)=UNKNOWN; 精力变化(milli)=UNKNOWN; 金钱变化(cents)=UNKNOWN; 模拟分钟=UNKNOWN; 工作分钟变化=UNKNOWN|净饥饿降低(milli)=600; 精力变化(milli)=0; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→UNKNOWN / home→restaurant|库存:UNKNOWN:UNKNOWN; 媒体:UNKNOWN:新增集=UNKNOWN,播放位变化=UNKNOWN; 游戏:UNKNOWN:UNKNOWN; 工作:UNKNOWN:UNKNOWN; 已核购买/消费:UNKNOWN/UNKNOWN / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0, '10': 0, '100': 0, '101': 0, '102': 0, '103': 0, '104': 0, '105': 0, '106': 0, '107': 0, '108': 0, '109': 0, '11': 0, '110': 0, '111': 0, '112': 0, '113': 0, '114': 0, '115': 0, '116': 0, '117': 0, '118': 0, '119': 0, '12': 0, '120': 0, '13': 0, '14': 0, '15': 0, '16': 0, '17': 0, '18': 0, '19': 0, '2': 0, '20': 0, '21': 0, '22': 0, '23': 0, '24': 0, '25': 0, '26': 0, '27': 0, '28': 0, '29': 0, '3': 0, '30': 0, '31': 0, '32': 0, '33': 0, '34': 0, '35': 0, '36': 0, '37': 0, '38': 0, '39': 0, '4': 0, '40': 0, '41': 0, '42': 0, '43': 0, '44': 0, '45': 0, '46': 0, '47': 0, '48': 0, '49': 0, '5': 0, '50': 0, '51': 0, '52': 0, '53': 0, '54': 0, '55': 0, '56': 0, '57': 0, '58': 0, '59': 0, '6': 0, '60': 0, '61': 0, '62': 0, '63': 0, '64': 0, '65': 0, '66': 0, '67': 0, '68': 0, '69': 0, '7': 0, '70': 0, '71': 0, '72': 0, '73': 0, '74': 0, '75': 0, '76': 0, '77': 0, '78': 0, '79': 0, '8': 0, '80': 0, '81': 0, '82': 0, '83': 0, '84': 0, '85': 0, '86': 0, '87': 0, '88': 0, '89': 0, '9': 0, '90': 0, '91': 0, '92': 0, '93': 0, '94': 0, '95': 0, '96': 0, '97': 0, '98': 0, '99': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):UNKNOWN; 精力变化(milli):UNKNOWN; 金钱变化(cents):UNKNOWN; 模拟分钟:UNKNOWN; 工作分钟变化:UNKNOWN|False/BACKEND_UNKNOWN/A_PROVIDER_TIMEOUT|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p015/s07/ACTIVITY_LOCATION/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|600→615 / 600→45|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p016/s12/MEAL_SUPPLY/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_bread/DECISION_ACCEPTED/完成=True|800→815 / 800→495|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_bread': 1}/{'food_bread': 1}|净饥饿降低(milli):320; 精力变化(milli):-30; 金钱变化(cents):-1200; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p017/s04/POST_MEAL_NEED/1|MEAL/food_meal/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|245→0 / 245→0|净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|restaurant→restaurant / restaurant→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):0; 精力变化(milli):0; 金钱变化(cents):0; 模拟分钟:0; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p018/s02/OWNERSHIP/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p019/s05/MEDIA_PROGRESS/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|810→825 / 810→255|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p020/s03/POST_MEAL_NEED/1|MEAL/food_meal/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|815→245 / 815→245|净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|restaurant→restaurant / restaurant→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):0; 精力变化(milli):0; 金钱变化(cents):0; 模拟分钟:0; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p021/s04/POST_MEAL_NEED/2|MEAL/food_meal/DECISION_ACCEPTED/完成=True|UNKNOWN/PROVIDER_TIMEOUT/完成=UNKNOWN|245→0 / 245→UNKNOWN|净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0|净饥饿降低(milli)=UNKNOWN; 精力变化(milli)=UNKNOWN; 金钱变化(cents)=UNKNOWN; 模拟分钟=UNKNOWN; 工作分钟变化=UNKNOWN|restaurant→restaurant / restaurant→UNKNOWN|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1} / 库存:UNKNOWN:UNKNOWN; 媒体:UNKNOWN:新增集=UNKNOWN,播放位变化=UNKNOWN; 游戏:UNKNOWN:UNKNOWN; 工作:UNKNOWN:UNKNOWN; 已核购买/消费:UNKNOWN/UNKNOWN|净饥饿降低(milli):UNKNOWN; 精力变化(milli):UNKNOWN; 金钱变化(cents):UNKNOWN; 模拟分钟:UNKNOWN; 工作分钟变化:UNKNOWN|False/BACKEND_UNKNOWN/B_PROVIDER_TIMEOUT|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p022/s08/ACTIVITY_LOCATION/1|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|615→630 / 615→60|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|office→restaurant / office→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p023/s01/OWNERSHIP/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|800→815 / 800→245|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|
|p024/s05/MEDIA_PROGRESS/2|TRAVEL/restaurant/DECISION_ACCEPTED/完成=True|MEAL/food_meal/DECISION_ACCEPTED/完成=True|810→825 / 810→255|净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0|净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0|home→restaurant / home→restaurant|库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{}/{} / 库存:OBSERVED:{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}; 媒体:NOT_EXERCISED:新增集=[],播放位变化={'1': 0}; 游戏:NOT_EXERCISED:{'game_a': 0}; 工作:NOT_EXERCISED:0; 已核购买/消费:{'food_meal': 1}/{'food_meal': 1}|净饥饿降低(milli):570; 精力变化(milli):-30; 金钱变化(cents):-2000; 模拟分钟:30; 工作分钟变化:0|True/BACKEND_MATCH/无|已观测单决策净后果；不支持未来动作/因果机制/人类最优|

## 描述性统计（全部配对分母保留）

|范围|指标|mean|median|min|max|正/负/平|已知/计划|缺失|
|---|---|---:|---:|---:|---:|---|---|---:|
|整体各臂23个已知/24分配/A|净饥饿降低(milli)|83.913|-15|-15|570|5/17/1|23/24|1|
|整体各臂23个已知/24分配/A|精力变化(milli)|-18.261|-15|-45|0|0/22/1|23/24|1|
|整体各臂23个已知/24分配/A|金钱变化(cents)|-434.783|0|-2000|0|0/5/18|23/24|1|
|整体各臂23个已知/24分配/A|模拟分钟|18.913|15|15|45|23/0/0|23/24|1|
|整体各臂23个已知/24分配/A|工作分钟变化|0|0|0|0|0/0/23|23/24|1|
|整体各臂23个已知/24分配/B|净饥饿降低(milli)|503.261|555|245|600|23/0/0|23/24|1|
|整体各臂23个已知/24分配/B|精力变化(milli)|-39.130|-45|-45|0|0/21/2|23/24|1|
|整体各臂23个已知/24分配/B|金钱变化(cents)|-1860.870|-2000|-2000|-1200|0/23/0|23/24|1|
|整体各臂23个已知/24分配/B|模拟分钟|43.043|45|30|45|23/0/0|23/24|1|
|整体各臂23个已知/24分配/B|工作分钟变化|0|0|0|0|0/0/23|23/24|1|
|整体各臂23个已知/24分配/B_minus_A|净饥饿降低(milli)|422.273|570.000|0|600|18/0/4|22/24|2|
|整体各臂23个已知/24分配/B_minus_A|精力变化(milli)|-23.182|-30.000|-30|0|0/17/5|22/24|2|
|整体各臂23个已知/24分配/B_minus_A|金钱变化(cents)|-1490.909|-2000.000|-2000|0|0/18/4|22/24|2|
|整体各臂23个已知/24分配/B_minus_A|模拟分钟|24.545|30.000|0|30|18/0/4|22/24|2|
|整体各臂23个已知/24分配/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/22|22/24|2|
|完整22对各臂（B−A仍保留24对分母）/A|净饥饿降低(milli)|76.591|-15.000|-15|570|4/17/1|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/A|精力变化(milli)|-17.727|-15.000|-45|0|0/21/1|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/A|金钱变化(cents)|-363.636|0.000|-2000|0|0/4/18|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/A|模拟分钟|18.409|15.000|15|45|22/0/0|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/A|工作分钟变化|0|0.000|0|0|0/0/22|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B|净饥饿降低(milli)|498.864|555.000|245|600|22/0/0|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B|精力变化(milli)|-40.909|-45.000|-45|0|0/21/1|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B|金钱变化(cents)|-1854.545|-2000.000|-2000|-1200|0/22/0|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B|模拟分钟|42.955|45.000|30|45|22/0/0|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B|工作分钟变化|0|0.000|0|0|0/0/22|22/22|0|
|完整22对各臂（B−A仍保留24对分母）/B_minus_A|净饥饿降低(milli)|422.273|570.000|0|600|18/0/4|22/24|2|
|完整22对各臂（B−A仍保留24对分母）/B_minus_A|精力变化(milli)|-23.182|-30.000|-30|0|0/17/5|22/24|2|
|完整22对各臂（B−A仍保留24对分母）/B_minus_A|金钱变化(cents)|-1490.909|-2000.000|-2000|0|0/18/4|22/24|2|
|完整22对各臂（B−A仍保留24对分母）/B_minus_A|模拟分钟|24.545|30.000|0|30|18/0/4|22/24|2|
|完整22对各臂（B−A仍保留24对分母）/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/22|22/24|2|
|OWNERSHIP/A|净饥饿降低(milli)|127.500|-15.000|-15|555|1/3/0|4/4|0|
|OWNERSHIP/A|精力变化(milli)|-22.500|-15.000|-45|-15|0/4/0|4/4|0|
|OWNERSHIP/A|金钱变化(cents)|-500|0.000|-2000|0|0/1/3|4/4|0|
|OWNERSHIP/A|模拟分钟|22.500|15.000|15|45|4/0/0|4/4|0|
|OWNERSHIP/A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|OWNERSHIP/B|净饥饿降低(milli)|555|555.000|555|555|4/0/0|4/4|0|
|OWNERSHIP/B|精力变化(milli)|-45|-45.000|-45|-45|0/4/0|4/4|0|
|OWNERSHIP/B|金钱变化(cents)|-2000|-2000.000|-2000|-2000|0/4/0|4/4|0|
|OWNERSHIP/B|模拟分钟|45|45.000|45|45|4/0/0|4/4|0|
|OWNERSHIP/B|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|OWNERSHIP/B_minus_A|净饥饿降低(milli)|427.500|570.000|0|570|3/0/1|4/4|0|
|OWNERSHIP/B_minus_A|精力变化(milli)|-22.500|-30.000|-30|0|0/3/1|4/4|0|
|OWNERSHIP/B_minus_A|金钱变化(cents)|-1500|-2000.000|-2000|0|0/3/1|4/4|0|
|OWNERSHIP/B_minus_A|模拟分钟|22.500|30.000|0|30|3/0/1|4/4|0|
|OWNERSHIP/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|POST_MEAL_NEED/A|净饥饿降低(milli)|407.500|407.500|245|570|4/0/0|4/4|0|
|POST_MEAL_NEED/A|精力变化(milli)|-30|-30.000|-30|-30|0/4/0|4/4|0|
|POST_MEAL_NEED/A|金钱变化(cents)|-2000|-2000.000|-2000|-2000|0/4/0|4/4|0|
|POST_MEAL_NEED/A|模拟分钟|30|30.000|30|30|4/0/0|4/4|0|
|POST_MEAL_NEED/A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|POST_MEAL_NEED/B|净饥饿降低(milli)|461.667|570|245|570|3/0/0|3/4|1|
|POST_MEAL_NEED/B|精力变化(milli)|-30|-30|-30|-30|0/3/0|3/4|1|
|POST_MEAL_NEED/B|金钱变化(cents)|-2000|-2000|-2000|-2000|0/3/0|3/4|1|
|POST_MEAL_NEED/B|模拟分钟|30|30|30|30|3/0/0|3/4|1|
|POST_MEAL_NEED/B|工作分钟变化|0|0|0|0|0/0/3|3/4|1|
|POST_MEAL_NEED/B_minus_A|净饥饿降低(milli)|0|0|0|0|0/0/3|3/4|1|
|POST_MEAL_NEED/B_minus_A|精力变化(milli)|0|0|0|0|0/0/3|3/4|1|
|POST_MEAL_NEED/B_minus_A|金钱变化(cents)|0|0|0|0|0/0/3|3/4|1|
|POST_MEAL_NEED/B_minus_A|模拟分钟|0|0|0|0|0/0/3|3/4|1|
|POST_MEAL_NEED/B_minus_A|工作分钟变化|0|0|0|0|0/0/3|3/4|1|
|MEDIA_PROGRESS/A|净饥饿降低(milli)|-10|-15|-15|0|0/2/1|3/4|1|
|MEDIA_PROGRESS/A|精力变化(milli)|-10|-15|-15|0|0/2/1|3/4|1|
|MEDIA_PROGRESS/A|金钱变化(cents)|0|0|0|0|0/0/3|3/4|1|
|MEDIA_PROGRESS/A|模拟分钟|15|15|15|15|3/0/0|3/4|1|
|MEDIA_PROGRESS/A|工作分钟变化|0|0|0|0|0/0/3|3/4|1|
|MEDIA_PROGRESS/B|净饥饿降低(milli)|577.500|577.500|555|600|4/0/0|4/4|0|
|MEDIA_PROGRESS/B|精力变化(milli)|-22.500|-22.500|-45|0|0/2/2|4/4|0|
|MEDIA_PROGRESS/B|金钱变化(cents)|-2000|-2000.000|-2000|-2000|0/4/0|4/4|0|
|MEDIA_PROGRESS/B|模拟分钟|45|45.000|45|45|4/0/0|4/4|0|
|MEDIA_PROGRESS/B|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEDIA_PROGRESS/B_minus_A|净饥饿降低(milli)|580|570|570|600|3/0/0|3/4|1|
|MEDIA_PROGRESS/B_minus_A|精力变化(milli)|-20|-30|-30|0|0/2/1|3/4|1|
|MEDIA_PROGRESS/B_minus_A|金钱变化(cents)|-2000|-2000|-2000|-2000|0/3/0|3/4|1|
|MEDIA_PROGRESS/B_minus_A|模拟分钟|30|30|30|30|3/0/0|3/4|1|
|MEDIA_PROGRESS/B_minus_A|工作分钟变化|0|0|0|0|0/0/3|3/4|1|
|ACTIVITY_LOCATION/A|净饥饿降低(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|ACTIVITY_LOCATION/A|精力变化(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|ACTIVITY_LOCATION/A|金钱变化(cents)|0|0.000|0|0|0/0/4|4/4|0|
|ACTIVITY_LOCATION/A|模拟分钟|15|15.000|15|15|4/0/0|4/4|0|
|ACTIVITY_LOCATION/A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|ACTIVITY_LOCATION/B|净饥饿降低(milli)|555|555.000|555|555|4/0/0|4/4|0|
|ACTIVITY_LOCATION/B|精力变化(milli)|-45|-45.000|-45|-45|0/4/0|4/4|0|
|ACTIVITY_LOCATION/B|金钱变化(cents)|-2000|-2000.000|-2000|-2000|0/4/0|4/4|0|
|ACTIVITY_LOCATION/B|模拟分钟|45|45.000|45|45|4/0/0|4/4|0|
|ACTIVITY_LOCATION/B|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|ACTIVITY_LOCATION/B_minus_A|净饥饿降低(milli)|570|570.000|570|570|4/0/0|4/4|0|
|ACTIVITY_LOCATION/B_minus_A|精力变化(milli)|-30|-30.000|-30|-30|0/4/0|4/4|0|
|ACTIVITY_LOCATION/B_minus_A|金钱变化(cents)|-2000|-2000.000|-2000|-2000|0/4/0|4/4|0|
|ACTIVITY_LOCATION/B_minus_A|模拟分钟|30|30.000|30|30|4/0/0|4/4|0|
|ACTIVITY_LOCATION/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_PAYMENT/A|净饥饿降低(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|MEAL_PAYMENT/A|精力变化(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|MEAL_PAYMENT/A|金钱变化(cents)|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_PAYMENT/A|模拟分钟|15|15.000|15|15|4/0/0|4/4|0|
|MEAL_PAYMENT/A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_PAYMENT/B|净饥饿降低(milli)|430|430.000|305|555|4/0/0|4/4|0|
|MEAL_PAYMENT/B|精力变化(milli)|-45|-45.000|-45|-45|0/4/0|4/4|0|
|MEAL_PAYMENT/B|金钱变化(cents)|-1600|-1600.000|-2000|-1200|0/4/0|4/4|0|
|MEAL_PAYMENT/B|模拟分钟|45|45.000|45|45|4/0/0|4/4|0|
|MEAL_PAYMENT/B|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_PAYMENT/B_minus_A|净饥饿降低(milli)|445|445.000|320|570|4/0/0|4/4|0|
|MEAL_PAYMENT/B_minus_A|精力变化(milli)|-30|-30.000|-30|-30|0/4/0|4/4|0|
|MEAL_PAYMENT/B_minus_A|金钱变化(cents)|-1600|-1600.000|-2000|-1200|0/4/0|4/4|0|
|MEAL_PAYMENT/B_minus_A|模拟分钟|30|30.000|30|30|4/0/0|4/4|0|
|MEAL_PAYMENT/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_SUPPLY/A|净饥饿降低(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|MEAL_SUPPLY/A|精力变化(milli)|-15|-15.000|-15|-15|0/4/0|4/4|0|
|MEAL_SUPPLY/A|金钱变化(cents)|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_SUPPLY/A|模拟分钟|15|15.000|15|15|4/0/0|4/4|0|
|MEAL_SUPPLY/A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_SUPPLY/B|净饥饿降低(milli)|430|430.000|305|555|4/0/0|4/4|0|
|MEAL_SUPPLY/B|精力变化(milli)|-45|-45.000|-45|-45|0/4/0|4/4|0|
|MEAL_SUPPLY/B|金钱变化(cents)|-1600|-1600.000|-2000|-1200|0/4/0|4/4|0|
|MEAL_SUPPLY/B|模拟分钟|45|45.000|45|45|4/0/0|4/4|0|
|MEAL_SUPPLY/B|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|
|MEAL_SUPPLY/B_minus_A|净饥饿降低(milli)|445|445.000|320|570|4/0/0|4/4|0|
|MEAL_SUPPLY/B_minus_A|精力变化(milli)|-30|-30.000|-30|-30|0/4/0|4/4|0|
|MEAL_SUPPLY/B_minus_A|金钱变化(cents)|-1600|-1600.000|-2000|-1200|0/4/0|4/4|0|
|MEAL_SUPPLY/B_minus_A|模拟分钟|30|30.000|30|30|4/0/0|4/4|0|
|MEAL_SUPPLY/B_minus_A|工作分钟变化|0|0.000|0|0|0/0/4|4/4|0|

## 成本与覆盖

- input_tokens：A均值381.818，B均值501.136；B−A=119.318；增幅31.250%；完整同后端已知配对22/24。
- latency_seconds：A均值10.070，B均值13.574；B−A=3.504；增幅34.798%；完整同后端已知配对22/24。

## 冻结提示干预审计

12场景/48单元state、observation、candidate和提示hash/字符/UTF-8字节核对PASS。
B system保持A完整字节前缀，追加116字符选择指令；用户事实与目的地相同，新增executable_options。
规范JSON键重排使A用户消息不是B字节前缀（共同前缀55字符）；不是只追加数据的单因子干预。
候选按(activity,target)字典序，null目标作空字符串排序，不是偏好排序。

|状态|候选数|活动出现次数|MEAL在全部TRAVEL前|提示字符A/B|提示字节A/B|
|---|---:|---|---|---|---|
|s01|10|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1236/1772|1270/1806|
|s02|11|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 1, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1236/1810|1270/1844|
|s03|7|{'CHORES': 0, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 0, 'PLAY': 0, 'SLEEP': 0, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1243/1659|1277/1693|
|s04|7|{'CHORES': 0, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 0, 'PLAY': 0, 'SLEEP': 0, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1245/1661|1279/1695|
|s05|10|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1238/1774|1272/1808|
|s06|9|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 0, 'WORK': 0}|True|1245/1740|1279/1774|
|s07|10|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1236/1772|1270/1806|
|s08|8|{'CHORES': 0, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 0, 'PLAY': 0, 'SLEEP': 0, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 1}|True|1239/1693|1273/1727|
|s09|10|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1234/1770|1268/1804|
|s10|9|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 1, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1234/1729|1268/1763|
|s11|10|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 2, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1234/1770|1268/1804|
|s12|9|{'CHORES': 1, 'LEISURE': 1, 'MEAL': 1, 'PERSONAL_CARE': 1, 'PLAY': 0, 'SLEEP': 1, 'TRAVEL': 3, 'WATCH': 1, 'WORK': 0}|True|1235/1730|1269/1764|

24个B分配的候选曝光：{'CHORES': 18, 'LEISURE': 24, 'MEAL': 44, 'PERSONAL_CARE': 18, 'PLAY': 2, 'SLEEP': 18, 'TRAVEL': 72, 'WATCH': 22, 'WORK': 2}。
TRAVEL曝光次数比MEAL多，数量本身不能解释B偏向MEAL；12/12场景MEAL排序在TRAVEL前。
候选列表未展开MEAL的准备→购买→进食宏步骤。
混杂：候选信息、明确选择指令、上下文长度、排列、活动名称重复、宏活动粒度。
不能分离因果机制；不读取completion/隐藏思考，不改提示后请求模型。

缺失token不补0，input/output/reasoning不相加，不推算人民币账单。
提示信息、额外选择指令、长度、候选顺序和活动曝光同时改变；没有分离因果机制。
真实有reasoning tokens，未证明关闭思考或小模型模拟。

## 七个研究问题

1. 零拒绝：两臂实际均选合法动作，合法选项较多且完成指标出现天花板；不证明提示等价。
2. A常出行：原提示显式列出TRAVEL和目的地，出行本身合法；这是可观察上下文，不是隐藏推理。
3. B常进食：候选数据、额外选择指令、曝光与排序可能共同影响；只提出机制假设。
4. 后果差异：见全部逐对delta及六家族统计；不得选择性报告。
5. 成本是否值得：输入与延迟增加已知；是否值得取决于尚未批准的需求、时间、资源目标。
6. 是否更符合需求：可比较净饥饿、精力、钱、时间，不等于整体生活最优，人工标准仍待审。
7. 下一阶段：先盲审任务目标与准备动作标准，再决定是否预注册独立提示分解实验，不自动执行。

## 人工审核与未来备选（未执行）

人工包隐藏条件标签并随机展示同态双案例；未伪造合理性分数或评审一致性。
待审：只保留原指标；多维需求而不合成总分；带目标并区分准备/终点；独立拆分提示干预。
未来候选臂：原RAW、仅候选数据、仅选择指令、紧凑候选、受控顺序/相近token预算。
以上没有实现或验证；新真实实验必须另立协议和授权。

## 完成标记

```text
EVALUATION_TYPE = EXPLORATORY_POST_HOC
NEW_REAL_PROVIDER_REQUESTS = 0
ORIGINAL_Q62_CONCLUSION = NO_CLEAR_DIFFERENCE
HUMAN_NEED_SATISFACTION_CONCLUSION = UNRESOLVED
HUMAN_REVIEW_COMPLETED = NO
HUMAN_REVIEW_PACKET = READY
LONG_TERM_HUMAN_LIKENESS = NOT_TESTED
SHORT_HORIZON_STATE_CONTINUITY = INSUFFICIENT_EVIDENCE
SOURCE_SESSION_VERIFIED = PASS
SOURCE_FILES_UNCHANGED = PASS
PLANNED_CELLS = 48
PLANNED_PAIRS = 24
FULLY_SCORED_PAIRS = 22
OBJECTIVE_DELTA_AUDIT = PASS
ACTION_GRANULARITY_AUDIT = PASS
PROMPT_INTERVENTION_AUDIT = PASS
```

## 本轮摘要、来源与复现

本轮M1.5是已有真实行为的离线审计，不是新模型实验。原session为q62-panel-real-v2-01，执行提交ae2123f50beaaca6bcac2dcca8e34659bd0a8b24；新分支从b7c6d503dc09c0c2d7dc32467b277a23a1a26404出发。PR #6仍OPEN，本轮另建stacked PR，不改原实验。

完整22对中，A/B平均净饥饿降低分别76.591/498.864 milli；平均精力变化−17.727/−40.909 milli；平均金钱变化−363.636/−1854.545 cents；平均模拟耗时18.409/42.955分钟。B−A的饥饿降低均值422.273、median570、range0..600，18正/0负/4平；精力变化均值−23.182、median−30、range−30..0，0正/17负/5平；金钱变化均值−1490.909、median−2000、range−2000..0，0正/18负/4平；耗时均值24.545、median30、range0..30，18正/0负/4平。完整覆盖22/24=91.667%，两侧各24分配/23已知，另两侧后果UNKNOWN。

这表现出一次决策后的需求、时间和资源权衡，不是B全面胜利。POST_MEAL_NEED完整3对全部持平；各臂原始均值受不同超时缺失样本影响，不能拿两臂未配对均值的差替代配对效应。两次重复来自相同12冻结状态，不是24名独立真人。

|家族|完整/计划对|净饥饿降低B−A|精力变化B−A|金钱变化B−A|模拟分钟B−A|
|---|---:|---:|---:|---:|---:|
|OWNERSHIP|4/4|427.5|−22.5|−1500|22.5|
|POST_MEAL_NEED|3/4|0|0|0|0|
|MEDIA_PROGRESS|3/4|580|−20|−2000|30|
|ACTIVITY_LOCATION|4/4|570|−30|−2000|30|
|MEAL_PAYMENT|4/4|445|−30|−1600|30|
|MEAL_SUPPLY|4/4|445|−30|−1600|30|

媒体/游戏/工作没有真实新选择，NOT_EXERCISED不是连续性或工作能力通过。game_a/series_a拥有量没有新增长；净库存大多为0，但只读领域账本核实MEAL中购买及消耗真实发生，不能以净0声称未吃。没有可靠前后值的字段保持UNKNOWN；两个超时未补0。模拟状态有0..1000的边界截断，不能把净delta精确拆成进食直接效应与时间效应，更不能映射真实人生理改善。

原首轮48客户端尝试、46HTTP、2超时、两臂各23完成/0拒绝、输入31.25%增幅及NO_CLEAR_DIFFERENCE不变。本轮新API请求0，原summary的runner字段不手改。完整22对输入+119.318 tokens/+31.25%，API延迟+3.504秒；全24对含超时延迟+3.103秒、提示字符+40.559%。原墙钟682.084438秒、API延迟合计674.443739秒、模拟时间合计1425分钟是不同轴，不相加。Token记录46/48，缺失2，不补账单、不猜费用；仍有reasoning tokens。

源297个普通文件全部流式SHA256核验，48个world和session SQLite以mode=ro&immutable=1/query_only读取，不迁移、不初始化、不重写。manifest/config/session/48计划/24配对、原summary/cells/paired、既有只读恢复与前次分析均一致；聚合文件清单hash：
`b72156ff956486cc1f56163037fc0bd588dd8917e1e68eb24ffcaf1df88af3f9`。
全部逐文件hash见[安全结果表](../reference/q62_outcome_audit_results.json)。journal只hash，不解码completion、prompt或隐藏推理；不读.env、不创建provider client。源缺失/证据不一致硬停止，不从中文报告伪造48行。

确定性审计在新目录保留-01/-02开发产物，再在独立未存在的-03目录完成最终审计；两者都不是模型重跑，原目录未变。最终输出为`run/evaluation/q62_outcome_audit/q62-real-v2-outcome-audit-03/`，含source_integrity、48行state_deltas、24对paired_effects、prompt_intervention_audit、人审包、私有解盲键、report和safe_delivery。解盲键只留忽略目录，不交给审核者，也不提交Git。大型源run/DB/原文/凭据不上传。

安全CLI示例（输出目录必须未存在；本轮无需再执行）：

```bash
python scripts/audit_q6_2_outcomes.py \
  --source-session run/evaluation/q6_2_fixed_state_panel/q62-panel-real-v2-01 \
  --output run/evaluation/q62_outcome_audit/your-new-offline-audit-id \
  --verify-integrity
```

默认也始终核验SHA256。没有provider权限参数，不读取环境key；既有恢复和分析默认查找相邻目录，可用只读路径参数明确指定。输出重用/与源重叠均拒绝。此程序只读已观测事实，不会补动作、修数据或调用模型。

[人工盲审包](q62_outcome_human_review.md)需在未阅读本页结果的独立审核者手中使用；行为合理/不合理/信息不足、事实理由、准备步骤、未来依赖和不确定性均待人工填写。已知本研究的人可能不再满足盲审条件。本轮HUMAN_REVIEW_COMPLETED=NO，不伪造评分或一致性。

原研究见[Q6.2档案](q62_action_projection.md)，本轮待决事项见[人工决策D-09](../review/decisions.md#d-09)，唯一[计划](../current/plan.md)及[验收](../current/acceptance.md)继续维护。各统计计算和安全边界由独立代码及离线测试支撑；最终提交对应的完整CI状态以PR检查与交付记录为准，不将历史通过数冒充新HEAD。
