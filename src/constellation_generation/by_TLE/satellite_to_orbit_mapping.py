'''

Author : yunanhou

Date : 2023/12/02

Function : The orbits within a shell are derived based on a clustering algorithm and the satellites are assigned to
           these orbits.

           Specifically, before executing this script, the corresponding relationship between satellites and shells has
           been established, but the relationship between satellites and orbit points has not yet been established. The
           function of this script is to establish the corresponding relationship between satellites and orbit.

           The main function of the script needs to pass in a shell class object, and then cluster the raan of each
           satellite in the shell object to obtain several orbits, and then assign all satellites in the shell to these
           orbits.

'''
import jenkspy
import src.TLE_constellation.constellation_entity.orbit as ORBIT
import matplotlib.pyplot as plt

# Parameter :
# shells : a collection of shell objects that have established corresponding relationships
# Return Value :
# after the function is executed, the mapping relationship between satellite, orbit, and shell has been established
# without any return value.
def satellite_to_orbit_mapping(shells):
    # 预定义每个shell的轨道数量（对应7个shell，共8个值，可能存在笔误，这里假设使用前7个值）
    predefined_orbit_counts = [1, 7, 5, 22, 30, 28, 28,32]

    for index, sh in enumerate(shells):
        # 确保有足够的预定义值
        if index >= len(predefined_orbit_counts):
            raise ValueError(f"预定义轨道数量不足，需要为第{index + 1}个shell提供值")

        orbits_number = predefined_orbit_counts[index]

        # 提取当前shell中所有卫星的RAAN值
        raans = [sat.tle_json["RA_OF_ASC_NODE"] for sat in sh.satellites]
        raans = sorted(raans)

        # 移除绘图和用户交互部分
        # 使用Jenks自然断点法进行聚类
        breaks = jenkspy.jenks_breaks(values=raans, n_classes=orbits_number)
        orbit_raans = [(breaks[i], breaks[i + 1]) for i in range(len(breaks) - 1)]

        # 创建轨道并分配卫星
        for ra_index, ra in enumerate(orbit_raans):
            lower_bound, upper_bound = ra
            orbit = ORBIT.orbit(shell=sh, raan_lower_bound=lower_bound, raan_upper_bound=upper_bound)

            for sat in sh.satellites:
                sat_raan = sat.tle_json["RA_OF_ASC_NODE"]
                # 处理第一个区间（包含下界）和其他区间（不包含下界）
                if (ra_index == 0 and lower_bound <= sat_raan <= upper_bound) or \
                        (ra_index > 0 and lower_bound < sat_raan <= upper_bound):
                    sat.orbit = orbit
                    orbit.satellites.append(sat)

            sh.orbits.append(orbit)