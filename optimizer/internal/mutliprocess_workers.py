"""
Exam Scheduler Web-UI  
Tsugunobu Miyake, Luke Snyder. 2025

Contains multiprocess workers for the exam scheduling optimization.
"""

import os
import django
import random
import copy
from datetime import datetime


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ExamScheduling.settings")
django.setup()

from django.conf import settings

def init_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ExamScheduling.settings')
    django.setup()

def SCIP_phase1_worker(optimizer, num_courses, num_exam_slots, grasp_solution, time_minimum, results, penalties, warm_start_grasp):
        """
        multiprocess function to solve phase1 using SCIP
        param optimizer: ExamOptimizer object used to reference information and create the SCIP model
        param num_courses: number of courses to solve phase1 with
        param num_exam_slots: number of exam slots the semester has
        param grasp_solution: an incomplete schedule used to warm start SCIP. As SCIP says, this "may or may not be ignored"
        param time_minimum: minimum number of seconds that SCIP will try and solve phase1
        param results: multiprocess dict to store the output of this function. output is stored in the format {phase1_cost:phase1_solution}
        param penalties: dict of the form {string of problem: float penalty associated with the problem}
        param warm_start_grasp: boolean as to whether to run grasp and use it to suggest a solution to scip
        returns: None, results is used to pull info out
        """
        init_django()
        large_courses = optimizer.choose_large_classes(num_courses)
        grasp_pairs, grasp_schedule = optimizer.grasp_pair_creation(large_courses)
        group_sizes = optimizer.model_creator.params["N_s"]
        max_size = settings.MAX_STUDENTS_PER_SLOT
        for g in optimizer.model_creator.params["G"]:
            max_size = group_sizes[g] if group_sizes[g] > max_size else max_size
        
        SCIP_model = optimizer.model_creator.create_phase1_SCIP_model(optimizer.group2slot, optimizer.no_groupslot, num_courses, time_minimum, penalties)
        SCIP_model.hideOutput()
        if warm_start_grasp:
            grasp_solution, grasp_cost = single_process_grasp_solver(num_courses, grasp_pairs, grasp_schedule, penalties, optimizer.model_creator.params, max_size, time_minimum)
            partial_solution = SCIP_model.createPartialSol()
            variables = SCIP_model.getVars()
            for group in grasp_solution:
                timeslot = grasp_solution[group]
                found = False
                for current in variables:
                    if (current.name == "x_gt[" + str(group) + "," + str(timeslot) + "]"):
                        found = True
                        SCIP_model.setSolVal(partial_solution, current, 1)
                        break
                if (not found):
                    print("failed to find variable named:", "x_gt[" + str(group) + "," + str(timeslot) + "]")


        print("beginning phase one solve with {} classes".format(num_courses))
        SCIP_model.optimize()
        if (SCIP_model.getStatus() == "infeasible"):
            results[-1] = 0
            return
        print("----------------\nphase 1 using {} courses: {}\n----------------".format(num_courses, SCIP_model.getObjVal()))

        SCIP_group2slot, SCIP_partial_solution = optimizer.get_SCIP_group2slot(SCIP_model, num_exam_slots)
        results[(SCIP_model.getObjVal(), num_courses)] = SCIP_group2slot

def SCIP_phase2_worker(optimizer, preference_profile, group2slot, num_exam_slots, results, num_courses, output_dir):
    """
    multiprocess function to do the final optimization and produce a full schedule that can be displayed
    param optimizer: ExamOptimizer object used to reference information and create the SCIP model
    param preference_profile: dict of the form {string of problem: float penalty associated with the problem}
    param group2slot: dict of the form {group:timeslot} produced by phase1. Used to create constraints to narrow down the problem such that it can be solved in the lifetime of the universe
    param num_exam_slots: number of exam slots the semester has
    param results: multiprocess dict to store the output of this function. output is stored in the format {phase1_cost:phase1_solution}
    returns: None, results is used to pull info out
    """
    SCIP_model = optimizer.model_creator.create_phase2_SCIP_model(preference_profile, num_courses, output_dir)
    variables = SCIP_model.getVars()
    for group in group2slot:
        timeslot = group2slot[group]
        found = False
        for current in variables:
            if (current.name == "x_gt[" + str(group) + "," + str(timeslot) + "]"):
                found = True
                SCIP_model.addCons((current == 1), str(group) + "_constraint")
                break
        if (not found):
            print("failed to find variable named:", "x_gt[" + str(group) + "," + str(timeslot) + "]")

    # SCIP_model.hideOutput()
    SCIP_model.setRealParam("limits/time", settings.PHASE_2_TIME_LIMIT)
    SCIP_model.optimize()
    if (SCIP_model.getStatus() == "infeasible"):
        results[-1] = 0
        return
    
    print("-----------------------\nOptimal value phase 2:", SCIP_model.getObjVal(), "\n-----------------------")

    SCIP_group2slot, SCIP_partial_solution = optimizer.get_SCIP_group2slot(SCIP_model, num_exam_slots)
    results[SCIP_model.getObjVal()] = SCIP_group2slot

def multi_process_grasp_solver(id, pairs, schedule, penalties, params, max_group_size, seconds_limit, smoothing, results, num_courses):
    """
    multiprocess function that uses grasp to solve phase1
    param pairs: list of grasp_pairs that represent all combinations of (group, timeslot) to be optimized
    param schedule: dict of the form {timeslot: [groups_at_this_time]}. has initial constraints inside it already if any exist
    param penalties: dict of the form {string of problem: float penalty associated with the problem}
    param params: dict of the form {string: data} stolen from the model_creator, since I need a a couple of the stuff in it
    param max_group_size: max number of studets that can be in a single group
    param seconds_limit: number of seconds that this function will run grasp solutions
    param smoothing: value that makes the grasp placement more random... supposedly... its pretty bad... higher value is more random
    param results: multiprocess dict used to extract the output
    returns: none, see results
    """
    winner = None
    winning_cost = float('inf')
    
    start = datetime.now()
    while (datetime.now() - start).total_seconds() < seconds_limit:
        output, cost, placed = grasp_placement(copy.deepcopy(pairs), copy.deepcopy(schedule), penalties, params, max_group_size, smoothing)

        if (cost < winning_cost):
            print("id: {}, old: {}, new: {}, time: {}, smoothness: {}".format(id, winning_cost, cost, datetime.now() - start, smoothing))
            winner = output
            winning_cost = cost  
           
    results[(winning_cost, num_courses)] = winner
    
def single_process_grasp_solver(id, pairs, schedule, penalties, params, max_group_size, seconds_limit, smoothing = 0):
    """
    single process function that uses grasp to solve phase1
    param pairs: list of grasp_pairs that represent all combinations of (group, timeslot) to be optimized
    param schedule: dict of the form {timeslot: [groups_at_this_time]}. has initial constraints inside it already if any exist
    param penalties: dict of the form {string of problem: float penalty associated with the problem}
    param params: dict of the form {string: data} stolen from the model_creator, since I need a a couple of the stuff in it
    param max_group_size: max number of studets that can be in a single group
    param seconds_limit: number of seconds that this function will run grasp solutions
    param smoothing: value that makes the grasp placement more random... supposedly... its pretty bad... higher value is more random
    returns: dict of the form {course:timeslot} and the cost of the schedule it found
    """
    winner = None
    winning_cost = float('inf')
    win_pairs = []
    start = datetime.now()
    while (datetime.now() - start).total_seconds() < seconds_limit:
        output, cost, new_pairs = grasp_placement(copy.deepcopy(pairs), copy.deepcopy(schedule), penalties, params, max_group_size, smoothing)

        if (cost < winning_cost):
            print("id: {}, old: {}, new: {}, time: {}, smoothness: {}".format(id, winning_cost, cost, datetime.now() - start, smoothing))
            winner = output
            winning_cost = cost  
            win_pairs = new_pairs
    
    check_grasp_solution(winner, schedule, params, penalties, win_pairs, winning_cost)
    
    output_format = dict()
    for key in winner:
        for group in winner[key]:
            output_format[group] = key
    return output_format, winning_cost

def check_grasp_solution(winner, schedule, params, penalties, win_pairs, winning_cost):
    """
    method to verify a grasp solution by manually computing the cost of the schedule and comparing it to what grasp says
    """
    intersect = params["N_s"]
    night_time_slots = params["n"]
    over_lis = []
    overlap = 0
    b2b = 0
    n2m = 0
    #overlaps
    for timeslot in winner:
        for group1 in winner[timeslot]:
            for group2 in winner[timeslot]:
                if group1 == group2:
                    continue
                overlap += intersect[group1, group2]
                if intersect[group1, group2] > 0:
                    over_lis.append((group1, group2, intersect[group1, group2]))
    
    for timeslot in winner:
        if timeslot + 1 in schedule.keys() and night_time_slots[timeslot] == 0:
            for group1 in winner[timeslot]:
                for group2 in winner[timeslot + 1]:
                    if group1 == group2:
                        continue
                    b2b += intersect[group1, group2]
        if timeslot - 1 in schedule.keys() and night_time_slots[timeslot] == 0:
            for group1 in winner[timeslot]:
                for group2 in winner[timeslot - 1]:
                    if group1 == group2:
                        continue
                    b2b += intersect[group1, group2]
    #n2m (night-to-morning)
    ## placing at night which might conflict with the morning slot.
        if timeslot + 1 in schedule.keys() and night_time_slots[timeslot] == 1:
            for group1 in winner[timeslot]:
                for group2 in winner[timeslot + 1]:
                    if group1 == group2:
                        continue
                    n2m += intersect[group1, group2]

    ## placing at morning which might conflict with the night slot.
        if timeslot - 1 in schedule.keys() and night_time_slots[timeslot - 1] == 1:
            for group1 in winner[timeslot]:
                for group2 in winner[timeslot - 1]:
                    if group1 == group2:
                        continue
                    n2m += intersect[group1, group2]
    comp_cost = penalties["overlap"] * overlap + penalties["B2B"] * b2b + penalties["PMtoAM"] * n2m
    pair_overlap = 0
    pair_b2b = 0
    pair_n2m = 0
    for pair in win_pairs:
        print("pair:", pair)
        pair_overlap += pair.overlap
        pair_b2b += pair.b2b
        pair_n2m += pair.n2m
    print("----------------------------")
    print(f"ACTUAL overlaps: {overlap/2}, b2b: {b2b/2}, n2m: {n2m/2}, comp_cost: {comp_cost/2}")
    print(f"PAIRS  overlaps: {pair_overlap}, b2b: {pair_b2b}, n2m: {pair_n2m}, win_cost: {winning_cost}")
    print(f"overlap sources", over_lis)
    print("----------------------------")

def grasp_placement(pairs, schedule, penalties, params, max_group_size, smoothing):
    total_cost = 0
    valid_slots = params["d"]
    timeslots = [key for key in valid_slots if valid_slots[key] == 1]
    #place largest group randomly
    random_slot = random.choice(timeslots)
    max_pair = max(pairs, key=lambda pair: pair.group_size)
    for pair in pairs:
        if pair.group == max_pair.group and pair.timeslot == random_slot:
            max_pair = pair
            break
    schedule[max_pair.timeslot].append(max_pair.group)
    pairs = remove_group(pairs, max_pair.group)
    placed = [max_pair]
    update_affected_pair_costs(pairs, max_pair, schedule, penalties, max_group_size, params)
    while pairs:
        next_pair = weighted_random_choice(pairs, smoothing=smoothing)
        schedule[next_pair.timeslot].append(next_pair.group)
        placed.append(next_pair)
        total_cost += next_pair.get_cost()
        pairs = remove_group(pairs, next_pair.group)
        update_affected_pair_costs(pairs, next_pair, schedule, penalties, max_group_size, params)
    return schedule, total_cost, placed

def update_affected_pair_costs(pairs, placed_pair, schedule, penalties, max_group_size, params):
    for pair in pairs:  
        if abs(placed_pair.timeslot - pair.timeslot) <= 1:
            update_pair_cost(pair, schedule, penalties, max_group_size, params)

def update_all_pair_costs(pairs, schedule, penalties, max_group_size, params):
    lis = []
    count = 0
    for pair in pairs:
        count += 1
        if update_pair_cost(pair, schedule, penalties, max_group_size, params):
            lis.append(pair)
    print("number of pairs that ran in all loop:", count)
    for pair in lis:
        print("changed by all updated:", pair)

    return lis

def update_pair_cost(pair, schedule, penalties, max_group_size, params):
    night_time_slots = params["n"]
    group_sizes = params["N_s"]
    cost = 0
    pair.overlap = 0
    pair.b2b = 0
    pair.n2m = 0
    pair.last_update = "None"
    #overlap
    for group in schedule[pair.timeslot]:
        cost += penalties["overlap"] * group_sizes[pair.group, group]
        pair.overlap += group_sizes[pair.group, group]

    # if there is an exam in front of it
    if pair.timeslot + 1 in schedule.keys():
        # If it is NOT a night exam, it might be in back-to-back
        if night_time_slots[pair.timeslot] == 0:
            for group in schedule[pair.timeslot + 1]:
                cost += penalties["B2B"] * group_sizes[pair.group, group]
                pair.b2b += group_sizes[pair.group, group]

        # If it is a night exam, it might be in night-to-morning
        else:
            for group in schedule[pair.timeslot + 1]:
                cost += penalties["PMtoAM"] * group_sizes[pair.group, group]
                pair.n2m += group_sizes[pair.group, group]

    # if there is an exam behind it
    if pair.timeslot - 1 in schedule.keys():
        # If it is NOT a night exam, it might be back-to-back
        if night_time_slots[pair.timeslot - 1] == 0:
            for group in schedule[pair.timeslot - 1]:
                cost += penalties["B2B"] * group_sizes[pair.group, group]
                pair.b2b += group_sizes[pair.group, group]
        # If it is a night exam, it might be night-to-morning
        else:
            for group in schedule[pair.timeslot - 1]:
                cost += penalties["PMtoAM"] * group_sizes[pair.group, group]
                pair.n2m += group_sizes[pair.group, group]
    
        

    
    #too many students per block
    total_students = 0
    for group in schedule[pair.timeslot]:
        total_students += group_sizes[group]
    if total_students + pair.group_size >= max_group_size:
        cost += float('inf')

    pair.update_cost(cost)

def weighted_random_choice(grasp_pairs, smoothing = 0):
    zero_cost_pairs = [gp for gp in grasp_pairs if gp.cost == 0]
    
    # If there are pairs with zero cost, choose from them equally
    if zero_cost_pairs:
        return random.choice(zero_cost_pairs)
    
    non_zero_pairs = [gp for gp in grasp_pairs if gp.cost != 0 and gp.cost != float('inf')]
    weights = [1 / (gp.cost + smoothing) for gp in non_zero_pairs]
    
    # Normalize weights to sum to 1
    total_weight = sum(weights)
    probabilities = [w / total_weight for w in weights]

    # Choose a GraspPair object based on the calculated probabilities
    chosen_pair = random.choices(non_zero_pairs, weights=probabilities, k=1)[0]
    return chosen_pair   
    

def remove_group(pairs, group):
    pairs = [gp for gp in pairs if gp.group != group]
    return pairs
