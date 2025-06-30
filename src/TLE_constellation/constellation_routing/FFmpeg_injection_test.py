from routing_policy_plugin_manager import routing_policy_plugin_manager
import src.TLE_constellation.constellation_entity.user as USER

# 1. 初始化路由管理器并设置插件
routing_manager = routing_policy_plugin_manager()
routing_manager.set_routing_policy('UDP_video_forwarding')

dT = 1000
constellation_name = "Starlink"
 
source = USER.user(116.397128, 39.916527, "Beijing")
#target = USER.user(117.52, 40.58, "chengde")
target = USER.user(-74.00, 40.43, "NewYork")

# 4. 执行视频转发插件
route = routing_manager.execute_routing_policy(
    constellation_name=constellation_name,
    source=source,
    target=target,
    sh=None,
    t=1
)


