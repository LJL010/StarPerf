'''

Author: yunanhou

Date : 2023/12/16

Function : the least hop path routing test cases at two locations under Constellation +Gird working mode

'''
import sys
from pathlib import Path
from datetime import datetime
import concurrent.futures

# 获取项目根目录（假设src目录的上一级是项目根）
project_root = str(Path(__file__).resolve().parent.parent)
sys.path.append(project_root)
import src.TLE_constellation.constellation_entity.user as USER
import src.constellation_generation.by_TLE.constellation_configuration as constellation_configuration
import src.TLE_constellation.constellation_connectivity.connectivity_mode_plugin_manager as connectivity_mode_plugin_manager
import src.TLE_constellation.constellation_routing.routing_policy_plugin_manager as routing_policy_plugin_manager


def least_hop_path(node):
    dT = 1000
    constellation_name = "Starlink"
    # the source of the communication pair
    #source = USER.user(0.00, 51.30, "London")
    source = USER.user(116.41, 39.9, "Beijing")
    # the target of the communication pair
    target = USER.user(0.00, 51.30, "London")
    # target = USER.user(-74.00, 40.43, "NewYork")

    # generate the constellations
    constellation = constellation_configuration.constellation_configuration(dT, constellation_name=constellation_name)

    formatted_time1 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"第{node}构建后的时间1:", formatted_time1)
    print("the shells of constellation is:", constellation.shells)

    # initialize the connectivity mode plugin manager
    connectionModePluginManager = connectivity_mode_plugin_manager.connectivity_mode_plugin_manager()
    # execute the connectivity mode and build ISLs between satellites
    connectionModePluginManager.execute_connection_policy(constellation=constellation, dT=dT)

    formatted_time2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"第{node}构建后的时间2:", formatted_time2)

    # initialize the routing policy plugin manager
    routingPolicyPluginManager = routing_policy_plugin_manager.routing_policy_plugin_manager()
    # switch routing policy
    routingPolicyPluginManager.set_routing_policy("least_hop_path")
    # execute routing policy
    # todo:这里并没有壳层之间的配合，所以统计的最短跳数的结果肯定会少很多卫星
    for i in range(4):
        least_hop_path = routingPolicyPluginManager.execute_routing_policy(constellation.constellation_name, source,
                                                                           target, constellation.shells[4])
        print("\t\t\tThe least hop path from ", source.user_name, " to ", target.user_name, " is ", least_hop_path)


    formatted_time3 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"第{node}构建后的时间3:", formatted_time3)

    # print("\t\t\tThe least hop path from " , source.user_name  , " to " , target.user_name , " is " , least_hop_path)
    # # modify the source of the communication pair
    # target = USER.user(117.87, 40.95, "承德")
    # # execute routing policy
    # least_hop_path = routingPolicyPluginManager.execute_routing_policy(constellation.constellation_name, source,
    #                                                                    target, constellation.shells[4])
    # print("\t\t\tThe least hop path from " , source.user_name  , " to " , target.user_name , " is " , least_hop_path)


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        list(executor.map(least_hop_path, range(1)))
