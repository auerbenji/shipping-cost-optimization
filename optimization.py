# import packages
import os
import time
import numpy as np
import pandas as pd
import collections as col
import random as rd

# solver
import gurobipy as gp
from gurobipy import GRB

# to optimize with cleaning detergent and food separate:
det_separate = False
# and set w_R = 0, c_R = 0, SP = 0, N_c_P = 2 for food
# and set w_T = w_O = 0, c_T = c_O = 0, N_c_P = 1 for det


# loop
abo_vkr = np.arange(80, 1001, 20) # 501
printout = True
for abo in abo_vkr:
    # timing
    start_model_gen = time.perf_counter()

    ################## --------- User input --------- ##################
    # 240 Ltr Version = 48 N_T, 9 N_O, 5 N_R

    N_T = int(np.ceil(abo/4.5)) # 48 # Trockenmix (1 oatpack produces 4.5 ltrs each)
    N_O = int(np.ceil(abo/22.5)) # 9 # Oel (1 bottle oil producing 5 batches of 4.5 ltr each)
    N_R = int(np.ceil(abo/40.5)) # 5 # Reiniger (1 detergent bottle cleaning 9 batches of 4.5 ltr each)

    # weight
    w_T = 0.568 #0.568 #(kg) weight per oatpack
    w_O = 0.912 #0.912 #(kg) weight per oil bottle
    w_R = 1.300 #1.300 #(kg) weight per det bottle

    # cost per piece
    c_T =  1.35  # 1.50   # (EUR/piece) # costs per Oatpack
    c_O =  2.70  # 2.45   # (EUR/piece) # costs per Oil Bottle
    c_R =  9.45  #10.70   # (EUR/piece) # costs per Detergent Bottle (preliminary)

    # carrier costs and weight, including Zuschlaege, 1kg for carton
    SC = np.array([0, 3.62, 4.17, 4.83, 6.3, 6.85, 7.02,  7.29])
    SW = np.array([0, 1.5   , 3.5   , 8.5   , 13.5  , 18.5   ,23.5   ,30])
    SP = 3.5 # 3.5 (EUR) shipping penalty for LQ shipping

    # Warehouse costs (Gras Gruppe)
    N_c_P = 1 # number of species to be picked
    c_A = 4.5 # administration fee, paid once
    c_P = 0.9 # picking fee (pick is per product species)
    c_packing   = 0.75 # cost of packing goods in carton
    c_loading   = 0.85 # cost of transferring carton into LKW
    c_carton    = 1.25 # cost of carton
    c_warehouse = c_A + c_P*N_c_P # single time costs per customer and monthly abo
    c_parcel = c_packing + c_carton + c_loading # recurring costs per parcel

    # current folder
    pwdpath = os.getcwd()
    path2data = pwdpath + '/results-' + str(abo) + '-ltr-det.xlsx' # output document

    ############ --------- Shipping Costs optimization --------- ###########
    # Specify Number of Ingredients for Full Supply
    N_supply = [N_T, N_O, N_R]
    w_species =[w_T, w_O, w_R]
    c_species = [c_T, c_O, c_R]

    # Specify maximum weight per parcel (excl. packaging) and max parcels
    max_weight = SW[-1] # (kg)

    N_parcels = N_T + N_O + N_R
    N_species = 3
    parcels = list(range(N_parcels))
    species = list(range(N_species))

    N_categories = len(SC)
    categories = list(range(N_categories))

    # create model
    m = gp.Model()
    m.setParam("IntegralityFocus",1)

    # adding logic constraints
    dist_matrix = m.addVars(N_species,N_parcels, vtype= GRB.INTEGER, lb=0)
    m.addConstrs(sum(dist_matrix[s,p] for p in parcels )             == N_supply[s] for s in species) # shipping all goods
    # m.addConstrs(sum(dist_matrix[s,p]*w_species[s] for s in species ) <= max_weight  for p in parcels) # shipping withing weight limit ?? do i need this line when having line 93 ??
    # checked via A matrix

    # adding carrier cost constraints
    cost_cat = m.addVars(N_categories, N_parcels, vtype=GRB.BINARY)
    m.addConstrs(sum(cost_cat[c,p] for c in categories) == 1 for p in parcels) # only one cost category per parcel

    # find the correct cost category
    m.addConstrs(sum(dist_matrix[s,p]*w_species[s] for s in species) <= SW[0]*cost_cat[0,p] + max_weight*(1-cost_cat[0,p]) for p in parcels) # either the parcel is empty then the weight is zero, or the parcel is not empty, then its a max weight constraint
    for c in categories[1:]: # do not use first item in the list
        m.addConstrs(SW[c-1]*cost_cat[c,p] <= sum(dist_matrix[s,p]*w_species[s] for s in species) for p in parcels)
        m.addConstrs(sum(dist_matrix[s,p]*w_species[s] for s in species) <= SW[c]*cost_cat[c,p] + max_weight*(1-cost_cat[c,p]) for p in parcels)

    # bigM constrains for dangerous goods penalty
    p_R = m.addVars(N_parcels, vtype = GRB.BINARY)
    if det_separate:
        m.addConstrs(dist_matrix[0 ,p] <= N_T*(1-p_R[p]) for p in parcels)
        m.addConstrs(dist_matrix[1 ,p] <= N_O*(1-p_R[p]) for p in parcels)
    m.addConstrs(dist_matrix[2 ,p] <= N_R*p_R[p] for p in parcels)

    # parts of cost function
    # cost of goods
    CG = 1/abo * ( sum(sum(dist_matrix[s,p] for p in parcels)*c_species[s] for s in species) )
    # cost of warehouse
    CW = 1/abo * ( c_warehouse + c_parcel*sum(sum(cost_cat[c,p] for p in parcels) for c in categories[1:]) )
    # cost of carrier and penalty
    CC = 1/abo * ( sum(sum(cost_cat[c,p] for p in parcels)*SC[c] for c in categories) + SP*sum(p_R[p] for p in parcels) ) 

    # cost to serve = costs of goods + warehouse cost + carrier cost (inkl penalty)
    CTS = CG + CW + CC
    m.setObjective(CTS,GRB.MINIMIZE)
    m.setParam(GRB.Param.IntegralityFocus, 0) # setting to 1 makes sure zeros are actually zeros
    m.setParam('OutputFlag', 1 if printout == True else 0)
    end_model_gen = time.perf_counter()
    m.optimize()
    end_model_optim = time.perf_counter()

    # return values
    # cost of goods
    CG = 1/abo * ( sum(sum(dist_matrix[s,p].X for p in parcels)*c_species[s] for s in species) )
    # cost of warehouse
    CW = 1/abo * ( c_warehouse + c_parcel*sum(sum(cost_cat[c,p].X for p in parcels) for c in categories[1:]) )
    # cost of carrier and penalty
    CC = 1/abo * ( sum(sum(cost_cat[c,p].X for p in parcels)*SC[c] for c in categories) + SP*sum(p_R[p].X for p in parcels) ) 


    ############ --------- printing solution --------- ##############
    # Gather results as np array
    if m.status == GRB.OPTIMAL:   
        print(
        "Success pardner, it took",
        f"{end_model_gen - start_model_gen:.4f}", "[s] to generate, and",
        f"{end_model_optim - end_model_gen:.4f}", "[s] to optimize."
        )

        dist_matrix_array = np.zeros((N_species, N_parcels))
        for s in species:
            for p in parcels:
                dist_matrix_array[s,p] = dist_matrix[s,p].X

        cost_cat_array = np.zeros((N_categories, N_parcels))
        for c in categories:
            for p in parcels:
                cost_cat_array[c,p] = cost_cat[c,p].X
        num_parcels_used = cost_cat_array[1:,:].sum()

        p_R_array = np.zeros(N_parcels)
        for p in parcels:
            p_R_array[p] = p_R[p].X

        # Create an empty N x 2 array where the dtype is 'object' to store mixed types
        # create preliminary array
        objval_array = np.empty((13, 3), dtype=object)

        objval_array[0, 0]  = abo
        objval_array[0, 1] = 'ltr/abo'
        objval_array[0, 2] = 'abo subject to optimization'

        objval_array[1, 0] = m.ObjVal # Cost to serve
        objval_array[1, 1] = 'EUR/ltr'
        objval_array[1, 2] = 'cost to serve'

        objval_array[2, 0] = CG # costs of good
        objval_array[2, 1] = 'EUR/ltr'
        objval_array[2, 2] = 'cost of good'

        objval_array[3, 0]  = CW # costs of warehouse
        objval_array[3, 1] = 'EUR/ltr'
        objval_array[3, 2] = 'cost of warehouse'

        objval_array[4, 0]  = CC # cost of carrier incl penalty
        objval_array[4, 1] = 'EUR/ltr'
        objval_array[4, 2] = 'cost of carrier incl penalty'

        objval_array[5, 0]  = SP # shipping penalty
        objval_array[5, 1] = 'EUR/parcel'
        objval_array[5, 2] = 'cost of penalty'

        objval_array[6, 0]  = CG/m.ObjVal # proportion cost of good
        objval_array[6, 1] = '-'
        objval_array[6, 2] = 'CG of CTS'

        objval_array[7, 0]  = CW/m.ObjVal # proportion warehouse cost
        objval_array[7, 1] = '-'
        objval_array[7, 2] = 'CW of CTS'

        objval_array[8, 0]  = CC/m.ObjVal # proportion carrier and penalty cost
        objval_array[8, 1] = '-'
        objval_array[8, 2] = 'CC of CTS'

        objval_array[9, 0]  = end_model_gen-start_model_gen # model generations time
        objval_array[9, 1] = 's'
        objval_array[9, 2] = 'model gen time'

        objval_array[10, 0]  = end_model_optim-end_model_gen # model optimization time
        objval_array[10, 1] = 's'
        objval_array[10, 2] = 'model opt time'

        objval_array[11, 0]  = num_parcels_used # number of parcels used
        objval_array[11, 1] = '-'
        objval_array[11, 2] = 'total parcels shipped'

        objval_array[12, 0]  = m.ObjVal*abo/num_parcels_used # levelized parcel value
        objval_array[12, 1] = 'EUR/parcel'
        objval_array[12, 2] = 'levelized parcel value'

        # create placeholder array
        temp_array = np.empty((N_species,3),dtype=object)
        # add weights
        temp_array[:,0] = np.transpose(w_species)
        temp_array[:,1] = np.array(['kg', 'kg', 'kg'], dtype=object)
        temp_array[:,2] = np.array(['w_T', 'w_O', 'w_R'], dtype=object)
        objval_array = np.vstack((objval_array,temp_array))
        # add costs
        temp_array[:,0] = np.transpose(c_species)
        temp_array[:,1] = np.array(['EUR', 'EUR', 'EUR'], dtype=object)
        temp_array[:,2] = np.array(['c_T', 'c_O', 'c_R'], dtype=object)
        objval_array = np.vstack((objval_array,temp_array))
        # add species
        temp_array[:,0] = np.transpose(N_supply)
        temp_array[:,1] = np.array(['-', '-', '-'], dtype=object)
        temp_array[:,2] = np.array(['N_T', 'N_O', 'N_R'], dtype=object)
        objval_array = np.vstack((objval_array,temp_array))

        # resort, easier to read
        objval_array = objval_array[:,[0,2,1]]

        # resort to extract data-frame easily
        objval_array_2 = objval_array[:,[1,0]].T


        # convert to panda dataframe and write to excel
        with pd.ExcelWriter(path2data) as writer:

            # Write obj function value
            df = pd.DataFrame(objval_array)
            df.to_excel(writer, sheet_name='ObjVal')

            # Write obj function value transposed for easier visualization
            df = pd.DataFrame(objval_array_2)
            df.to_excel(writer, sheet_name='Visual')

            # Write dist and cost matrix
            df = pd.DataFrame(dist_matrix_array)
            df.to_excel(writer, sheet_name='dist')
            df = pd.DataFrame(cost_cat_array)
            df.to_excel(writer, sheet_name='cost_cat')

            # Write penalties
            df = pd.DataFrame(np.transpose(p_R_array))
            df.to_excel(writer, sheet_name='p_R')

            # Write cost and weight
            weight_cost_array = np.empty((len(SW), 3), dtype=object)
            weight_cost_array[:,2] = ['kg / EUR']
            weight_cost_array[:,[0,1]] = np.column_stack((SW, SC))
            df = pd.DataFrame(weight_cost_array)
            df.to_excel(writer, sheet_name='weight-and-cost')


        ## debugging


        # --------------------------------------------------------------------------
        # m.update()
        # A = m.getA()
        # sense = np.array(m.getAttr("Sense",m.getConstrs()))
        # RHS   = np.array(m.getAttr("RHS",m.getConstrs()))
        # path2debug = pwdpath + '/A-shipping cost 5.xlsx'
        # with pd.ExcelWriter(path2debug) as writer:
        #     df = pd.DataFrame(A.toarray())
        #     df.to_excel(writer, sheet_name='A')
        #     df = pd.DataFrame(sense)
        #     df.to_excel(writer, sheet_name='sense')
        #     df = pd.DataFrame(RHS)
        #     df.to_excel(writer, sheet_name='RHS')