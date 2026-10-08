# 同态双案例人工审核包

请独立评价实际事实；未提供标准答案，也不要求每对必须选优胜者。
顺序已随机化，条件标签及解盲键不在此包中；如果事先看过结果报告，不再保证盲审。
未作人工标注：HUMAN_REVIEW_COMPLETED=NO。缺失后果不可补零或猜测未来。

单位与方向：饥饿/精力是0..1000的合成milli状态，不是真人生理测量。
净饥饿降低=开始−结束，正数降低、负数增加；精力变化=结束−开始。
金钱单位cents，负向变化是支出但不自动错误；模拟分钟不是API延迟或墙钟秒。
TRAVEL的完成表示到达目的地；MEAL可按原规则包含旅行、购买、进食，粒度不同。
准备步骤不自动失败，最终进食不自动最优；未观测未来，不猜下一步。
初始资源来自同态冻结观测核对，不展示条件候选列表；供应与持有量分开。
购买/消费数来自只读账本与实际库存交叉核验，净库存0不代表没有消费。

## 双案例 r001

### 案例 1

初始模拟分钟：10；位置：home；钱(cents)：300000；饥饿/精力(milli)：810/690。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {'1': 10}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：10；位置：home；钱(cents)：300000；饥饿/精力(milli)：810/690。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {'1': 10}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r002

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：2000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：2000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r003

### 案例 1

初始模拟分钟：3600；位置：home；钱(cents)：300000；饥饿/精力(milli)：1000/0。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120], 'offsets': {'1': 30, '10': 30, '100': 30, '101': 30, '102': 30, '103': 30, '104': 30, '105': 30, '106': 30, '107': 30, '108': 30, '109': 30, '11': 30, '110': 30, '111': 30, '112': 30, '113': 30, '114': 30, '115': 30, '116': 30, '117': 30, '118': 30, '119': 30, '12': 30, '120': 30, '13': 30, '14': 30, '15': 30, '16': 30, '17': 30, '18': 30, '19': 30, '2': 30, '20': 30, '21': 30, '22': 30, '23': 30, '24': 30, '25': 30, '26': 30, '27': 30, '28': 30, '29': 30, '3': 30, '30': 30, '31': 30, '32': 30, '33': 30, '34': 30, '35': 30, '36': 30, '37': 30, '38': 30, '39': 30, '4': 30, '40': 30, '41': 30, '42': 30, '43': 30, '44': 30, '45': 30, '46': 30, '47': 30, '48': 30, '49': 30, '5': 30, '50': 30, '51': 30, '52': 30, '53': 30, '54': 30, '55': 30, '56': 30, '57': 30, '58': 30, '59': 30, '6': 30, '60': 30, '61': 30, '62': 30, '63': 30, '64': 30, '65': 30, '66': 30, '67': 30, '68': 30, '69': 30, '7': 30, '70': 30, '71': 30, '72': 30, '73': 30, '74': 30, '75': 30, '76': 30, '77': 30, '78': 30, '79': 30, '8': 30, '80': 30, '81': 30, '82': 30, '83': 30, '84': 30, '85': 30, '86': 30, '87': 30, '88': 30, '89': 30, '9': 30, '90': 30, '91': 30, '92': 30, '93': 30, '94': 30, '95': 30, '96': 30, '97': 30, '98': 30, '99': 30}, 'view_counts': {'1': 1, '10': 1, '100': 1, '101': 1, '102': 1, '103': 1, '104': 1, '105': 1, '106': 1, '107': 1, '108': 1, '109': 1, '11': 1, '110': 1, '111': 1, '112': 1, '113': 1, '114': 1, '115': 1, '116': 1, '117': 1, '118': 1, '119': 1, '12': 1, '120': 1, '13': 1, '14': 1, '15': 1, '16': 1, '17': 1, '18': 1, '19': 1, '2': 1, '20': 1, '21': 1, '22': 1, '23': 1, '24': 1, '25': 1, '26': 1, '27': 1, '28': 1, '29': 1, '3': 1, '30': 1, '31': 1, '32': 1, '33': 1, '34': 1, '35': 1, '36': 1, '37': 1, '38': 1, '39': 1, '4': 1, '40': 1, '41': 1, '42': 1, '43': 1, '44': 1, '45': 1, '46': 1, '47': 1, '48': 1, '49': 1, '5': 1, '50': 1, '51': 1, '52': 1, '53': 1, '54': 1, '55': 1, '56': 1, '57': 1, '58': 1, '59': 1, '6': 1, '60': 1, '61': 1, '62': 1, '63': 1, '64': 1, '65': 1, '66': 1, '67': 1, '68': 1, '69': 1, '7': 1, '70': 1, '71': 1, '72': 1, '73': 1, '74': 1, '75': 1, '76': 1, '77': 1, '78': 1, '79': 1, '8': 1, '80': 1, '81': 1, '82': 1, '83': 1, '84': 1, '85': 1, '86': 1, '87': 1, '88': 1, '89': 1, '9': 1, '90': 1, '91': 1, '92': 1, '93': 1, '94': 1, '95': 1, '96': 1, '97': 1, '98': 1, '99': 1}, 'next_episode': None, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=600; 精力变化(milli)=0; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：3600；位置：home；钱(cents)：300000；饥饿/精力(milli)：1000/0。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120], 'offsets': {'1': 30, '10': 30, '100': 30, '101': 30, '102': 30, '103': 30, '104': 30, '105': 30, '106': 30, '107': 30, '108': 30, '109': 30, '11': 30, '110': 30, '111': 30, '112': 30, '113': 30, '114': 30, '115': 30, '116': 30, '117': 30, '118': 30, '119': 30, '12': 30, '120': 30, '13': 30, '14': 30, '15': 30, '16': 30, '17': 30, '18': 30, '19': 30, '2': 30, '20': 30, '21': 30, '22': 30, '23': 30, '24': 30, '25': 30, '26': 30, '27': 30, '28': 30, '29': 30, '3': 30, '30': 30, '31': 30, '32': 30, '33': 30, '34': 30, '35': 30, '36': 30, '37': 30, '38': 30, '39': 30, '4': 30, '40': 30, '41': 30, '42': 30, '43': 30, '44': 30, '45': 30, '46': 30, '47': 30, '48': 30, '49': 30, '5': 30, '50': 30, '51': 30, '52': 30, '53': 30, '54': 30, '55': 30, '56': 30, '57': 30, '58': 30, '59': 30, '6': 30, '60': 30, '61': 30, '62': 30, '63': 30, '64': 30, '65': 30, '66': 30, '67': 30, '68': 30, '69': 30, '7': 30, '70': 30, '71': 30, '72': 30, '73': 30, '74': 30, '75': 30, '76': 30, '77': 30, '78': 30, '79': 30, '8': 30, '80': 30, '81': 30, '82': 30, '83': 30, '84': 30, '85': 30, '86': 30, '87': 30, '88': 30, '89': 30, '9': 30, '90': 30, '91': 30, '92': 30, '93': 30, '94': 30, '95': 30, '96': 30, '97': 30, '98': 30, '99': 30}, 'view_counts': {'1': 1, '10': 1, '100': 1, '101': 1, '102': 1, '103': 1, '104': 1, '105': 1, '106': 1, '107': 1, '108': 1, '109': 1, '11': 1, '110': 1, '111': 1, '112': 1, '113': 1, '114': 1, '115': 1, '116': 1, '117': 1, '118': 1, '119': 1, '12': 1, '120': 1, '13': 1, '14': 1, '15': 1, '16': 1, '17': 1, '18': 1, '19': 1, '2': 1, '20': 1, '21': 1, '22': 1, '23': 1, '24': 1, '25': 1, '26': 1, '27': 1, '28': 1, '29': 1, '3': 1, '30': 1, '31': 1, '32': 1, '33': 1, '34': 1, '35': 1, '36': 1, '37': 1, '38': 1, '39': 1, '4': 1, '40': 1, '41': 1, '42': 1, '43': 1, '44': 1, '45': 1, '46': 1, '47': 1, '48': 1, '49': 1, '5': 1, '50': 1, '51': 1, '52': 1, '53': 1, '54': 1, '55': 1, '56': 1, '57': 1, '58': 1, '59': 1, '6': 1, '60': 1, '61': 1, '62': 1, '63': 1, '64': 1, '65': 1, '66': 1, '67': 1, '68': 1, '69': 1, '7': 1, '70': 1, '71': 1, '72': 1, '73': 1, '74': 1, '75': 1, '76': 1, '77': 1, '78': 1, '79': 1, '8': 1, '80': 1, '81': 1, '82': 1, '83': 1, '84': 1, '85': 1, '86': 1, '87': 1, '88': 1, '89': 1, '9': 1, '90': 1, '91': 1, '92': 1, '93': 1, '94': 1, '95': 1, '96': 1, '97': 1, '98': 1, '99': 1}, 'next_episode': None, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：UNKNOWN；实际完成：UNKNOWN。
实际状态净变化：净饥饿降低(milli)=UNKNOWN; 精力变化(milli)=UNKNOWN; 金钱变化(cents)=UNKNOWN; 模拟分钟=UNKNOWN; 工作分钟变化=UNKNOWN。
实际净支出/收入(cents)：UNKNOWN/UNKNOWN；位置：home→UNKNOWN。
库存净变化：UNKNOWN；媒体覆盖：UNKNOWN；游戏覆盖：UNKNOWN；工作覆盖：UNKNOWN。

核实购买量：UNKNOWN；核实消费量：UNKNOWN。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r004

### 案例 1

初始模拟分钟：15；位置：restaurant；钱(cents)：300000；饥饿/精力(milli)：815/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：15；位置：restaurant；钱(cents)：300000；饥饿/精力(milli)：815/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r005

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': False}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': False}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_bread；实际完成：True。
实际状态净变化：净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：1200/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_bread': 1}；核实消费量：{'food_bread': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r006

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：297000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 1, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 1, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：297000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 1, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 1, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r007

### 案例 1

初始模拟分钟：15；位置：office；钱(cents)：300000；饥饿/精力(milli)：615/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：office→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：15；位置：office；钱(cents)：300000；饥饿/精力(milli)：615/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：office→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r008

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：1999；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：1999；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_bread；实际完成：True。
实际状态净变化：净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：1200/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_bread': 1}；核实消费量：{'food_bread': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r009

### 案例 1

初始模拟分钟：45；位置：restaurant；钱(cents)：298000；饥饿/精力(milli)：245/655。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：UNKNOWN；实际完成：UNKNOWN。
实际状态净变化：净饥饿降低(milli)=UNKNOWN; 精力变化(milli)=UNKNOWN; 金钱变化(cents)=UNKNOWN; 模拟分钟=UNKNOWN; 工作分钟变化=UNKNOWN。
实际净支出/收入(cents)：UNKNOWN/UNKNOWN；位置：restaurant→UNKNOWN。
库存净变化：UNKNOWN；媒体覆盖：UNKNOWN；游戏覆盖：UNKNOWN；工作覆盖：UNKNOWN。

核实购买量：UNKNOWN；核实消费量：UNKNOWN。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：45；位置：restaurant；钱(cents)：298000；饥饿/精力(milli)：245/655。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r010

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r011

### 案例 1

初始模拟分钟：45；位置：restaurant；钱(cents)：298000；饥饿/精力(milli)：245/655。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：45；位置：restaurant；钱(cents)：298000；饥饿/精力(milli)：245/655。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=245; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r012

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：1999；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_bread；实际完成：True。
实际状态净变化：净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：1200/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_bread': 1}；核实消费量：{'food_bread': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：1999；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r013

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：297000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 1, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 1, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：297000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 1, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 1, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r014

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：2000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：2000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r015

### 案例 1

初始模拟分钟：3600；位置：home；钱(cents)：300000；饥饿/精力(milli)：1000/0。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120], 'offsets': {'1': 30, '10': 30, '100': 30, '101': 30, '102': 30, '103': 30, '104': 30, '105': 30, '106': 30, '107': 30, '108': 30, '109': 30, '11': 30, '110': 30, '111': 30, '112': 30, '113': 30, '114': 30, '115': 30, '116': 30, '117': 30, '118': 30, '119': 30, '12': 30, '120': 30, '13': 30, '14': 30, '15': 30, '16': 30, '17': 30, '18': 30, '19': 30, '2': 30, '20': 30, '21': 30, '22': 30, '23': 30, '24': 30, '25': 30, '26': 30, '27': 30, '28': 30, '29': 30, '3': 30, '30': 30, '31': 30, '32': 30, '33': 30, '34': 30, '35': 30, '36': 30, '37': 30, '38': 30, '39': 30, '4': 30, '40': 30, '41': 30, '42': 30, '43': 30, '44': 30, '45': 30, '46': 30, '47': 30, '48': 30, '49': 30, '5': 30, '50': 30, '51': 30, '52': 30, '53': 30, '54': 30, '55': 30, '56': 30, '57': 30, '58': 30, '59': 30, '6': 30, '60': 30, '61': 30, '62': 30, '63': 30, '64': 30, '65': 30, '66': 30, '67': 30, '68': 30, '69': 30, '7': 30, '70': 30, '71': 30, '72': 30, '73': 30, '74': 30, '75': 30, '76': 30, '77': 30, '78': 30, '79': 30, '8': 30, '80': 30, '81': 30, '82': 30, '83': 30, '84': 30, '85': 30, '86': 30, '87': 30, '88': 30, '89': 30, '9': 30, '90': 30, '91': 30, '92': 30, '93': 30, '94': 30, '95': 30, '96': 30, '97': 30, '98': 30, '99': 30}, 'view_counts': {'1': 1, '10': 1, '100': 1, '101': 1, '102': 1, '103': 1, '104': 1, '105': 1, '106': 1, '107': 1, '108': 1, '109': 1, '11': 1, '110': 1, '111': 1, '112': 1, '113': 1, '114': 1, '115': 1, '116': 1, '117': 1, '118': 1, '119': 1, '12': 1, '120': 1, '13': 1, '14': 1, '15': 1, '16': 1, '17': 1, '18': 1, '19': 1, '2': 1, '20': 1, '21': 1, '22': 1, '23': 1, '24': 1, '25': 1, '26': 1, '27': 1, '28': 1, '29': 1, '3': 1, '30': 1, '31': 1, '32': 1, '33': 1, '34': 1, '35': 1, '36': 1, '37': 1, '38': 1, '39': 1, '4': 1, '40': 1, '41': 1, '42': 1, '43': 1, '44': 1, '45': 1, '46': 1, '47': 1, '48': 1, '49': 1, '5': 1, '50': 1, '51': 1, '52': 1, '53': 1, '54': 1, '55': 1, '56': 1, '57': 1, '58': 1, '59': 1, '6': 1, '60': 1, '61': 1, '62': 1, '63': 1, '64': 1, '65': 1, '66': 1, '67': 1, '68': 1, '69': 1, '7': 1, '70': 1, '71': 1, '72': 1, '73': 1, '74': 1, '75': 1, '76': 1, '77': 1, '78': 1, '79': 1, '8': 1, '80': 1, '81': 1, '82': 1, '83': 1, '84': 1, '85': 1, '86': 1, '87': 1, '88': 1, '89': 1, '9': 1, '90': 1, '91': 1, '92': 1, '93': 1, '94': 1, '95': 1, '96': 1, '97': 1, '98': 1, '99': 1}, 'next_episode': None, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=0; 精力变化(milli)=0; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：3600；位置：home；钱(cents)：300000；饥饿/精力(milli)：1000/0。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120], 'offsets': {'1': 30, '10': 30, '100': 30, '101': 30, '102': 30, '103': 30, '104': 30, '105': 30, '106': 30, '107': 30, '108': 30, '109': 30, '11': 30, '110': 30, '111': 30, '112': 30, '113': 30, '114': 30, '115': 30, '116': 30, '117': 30, '118': 30, '119': 30, '12': 30, '120': 30, '13': 30, '14': 30, '15': 30, '16': 30, '17': 30, '18': 30, '19': 30, '2': 30, '20': 30, '21': 30, '22': 30, '23': 30, '24': 30, '25': 30, '26': 30, '27': 30, '28': 30, '29': 30, '3': 30, '30': 30, '31': 30, '32': 30, '33': 30, '34': 30, '35': 30, '36': 30, '37': 30, '38': 30, '39': 30, '4': 30, '40': 30, '41': 30, '42': 30, '43': 30, '44': 30, '45': 30, '46': 30, '47': 30, '48': 30, '49': 30, '5': 30, '50': 30, '51': 30, '52': 30, '53': 30, '54': 30, '55': 30, '56': 30, '57': 30, '58': 30, '59': 30, '6': 30, '60': 30, '61': 30, '62': 30, '63': 30, '64': 30, '65': 30, '66': 30, '67': 30, '68': 30, '69': 30, '7': 30, '70': 30, '71': 30, '72': 30, '73': 30, '74': 30, '75': 30, '76': 30, '77': 30, '78': 30, '79': 30, '8': 30, '80': 30, '81': 30, '82': 30, '83': 30, '84': 30, '85': 30, '86': 30, '87': 30, '88': 30, '89': 30, '9': 30, '90': 30, '91': 30, '92': 30, '93': 30, '94': 30, '95': 30, '96': 30, '97': 30, '98': 30, '99': 30}, 'view_counts': {'1': 1, '10': 1, '100': 1, '101': 1, '102': 1, '103': 1, '104': 1, '105': 1, '106': 1, '107': 1, '108': 1, '109': 1, '11': 1, '110': 1, '111': 1, '112': 1, '113': 1, '114': 1, '115': 1, '116': 1, '117': 1, '118': 1, '119': 1, '12': 1, '120': 1, '13': 1, '14': 1, '15': 1, '16': 1, '17': 1, '18': 1, '19': 1, '2': 1, '20': 1, '21': 1, '22': 1, '23': 1, '24': 1, '25': 1, '26': 1, '27': 1, '28': 1, '29': 1, '3': 1, '30': 1, '31': 1, '32': 1, '33': 1, '34': 1, '35': 1, '36': 1, '37': 1, '38': 1, '39': 1, '4': 1, '40': 1, '41': 1, '42': 1, '43': 1, '44': 1, '45': 1, '46': 1, '47': 1, '48': 1, '49': 1, '5': 1, '50': 1, '51': 1, '52': 1, '53': 1, '54': 1, '55': 1, '56': 1, '57': 1, '58': 1, '59': 1, '6': 1, '60': 1, '61': 1, '62': 1, '63': 1, '64': 1, '65': 1, '66': 1, '67': 1, '68': 1, '69': 1, '7': 1, '70': 1, '71': 1, '72': 1, '73': 1, '74': 1, '75': 1, '76': 1, '77': 1, '78': 1, '79': 1, '8': 1, '80': 1, '81': 1, '82': 1, '83': 1, '84': 1, '85': 1, '86': 1, '87': 1, '88': 1, '89': 1, '9': 1, '90': 1, '91': 1, '92': 1, '93': 1, '94': 1, '95': 1, '96': 1, '97': 1, '98': 1, '99': 1}, 'next_episode': None, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=600; 精力变化(milli)=0; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r016

### 案例 1

初始模拟分钟：10；位置：home；钱(cents)：300000；饥饿/精力(milli)：810/690。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {'1': 10}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：10；位置：home；钱(cents)：300000；饥饿/精力(milli)：810/690。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {'1': 10}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r017

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r018

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：600/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：600/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r019

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r020

### 案例 1

初始模拟分钟：15；位置：office；钱(cents)：300000；饥饿/精力(milli)：615/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：office→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：15；位置：office；钱(cents)：300000；饥饿/精力(milli)：615/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：office→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r021

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r022

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：600/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=555; 精力变化(milli)=-45; 金钱变化(cents)=-2000; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：300000；饥饿/精力(milli)：600/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r023

### 案例 1

初始模拟分钟：15；位置：restaurant；钱(cents)：300000；饥饿/精力(milli)：815/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：15；位置：restaurant；钱(cents)：300000；饥饿/精力(milli)：815/685。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_meal；实际完成：True。
实际状态净变化：净饥饿降低(milli)=570; 精力变化(milli)=-30; 金钱变化(cents)=-2000; 模拟分钟=30; 工作分钟变化=0。
实际净支出/收入(cents)：2000/0；位置：restaurant→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_meal': 1}；核实消费量：{'food_meal': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

## 双案例 r024

### 案例 1

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': False}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：MEAL/food_bread；实际完成：True。
实际状态净变化：净饥饿降低(milli)=305; 精力变化(milli)=-45; 金钱变化(cents)=-1200; 模拟分钟=45; 工作分钟变化=0。
实际净支出/收入(cents)：1200/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{'food_bread': 1}；核实消费量：{'food_bread': 1}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________

### 案例 2

初始模拟分钟：0；位置：home；钱(cents)：5000；饥饿/精力(milli)：800/700。
初始库存：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体进度：{'series_a': {'watched': [], 'offsets': {}, 'view_counts': {}, 'next_episode': 1, 'total_episodes': 120}}；游戏分钟：{'game_a': 0}。
初始资源（拥有量/价格cents/可用/供应/时长）：[{'object_id': 'food_bread', 'owned_quantity': 0, 'price_cents': 1200, 'duration_minutes': 30, 'available': True, 'in_stock': True}, {'object_id': 'food_meal', 'owned_quantity': 0, 'price_cents': 2000, 'duration_minutes': 30, 'available': True, 'in_stock': False}, {'object_id': 'game_a', 'owned_quantity': 0, 'price_cents': 3000, 'duration_minutes': 45, 'available': True, 'in_stock': True}, {'object_id': 'series_a', 'owned_quantity': 0, 'price_cents': 0, 'duration_minutes': 30, 'available': True, 'in_stock': False}]。
活动/对象：TRAVEL/restaurant；实际完成：True。
实际状态净变化：净饥饿降低(milli)=-15; 精力变化(milli)=-15; 金钱变化(cents)=0; 模拟分钟=15; 工作分钟变化=0。
实际净支出/收入(cents)：0/0；位置：home→restaurant。
库存净变化：{'food_bread': 0, 'food_meal': 0, 'game_a': 0, 'series_a': 0}；媒体覆盖：NOT_EXERCISED；游戏覆盖：NOT_EXERCISED；工作覆盖：NOT_EXERCISED。

核实购买量：{}；核实消费量：{}。

判断：□行为合理 □不合理 □信息不足
判断理由：________；依赖的具体状态事实：________
是否视为准备步骤：________；判断是否依赖未来行为：________
不确定性与缺少的偏好/目标：________
