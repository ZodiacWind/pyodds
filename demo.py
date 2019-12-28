import numpy as np
import argparse
import time
import logging
import pandas as pd
import os
import io
import contextlib
import getpass
import warnings
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score,roc_auc_score
from pyodds.utils.utilities import output_performance,insert_demo_data,connect_server,query_data
from pyodds.utils.importAlgorithm import algorithm_selection
from pyodds.utils.plotUtils import visualize_distribution_static,visualize_distribution_time_serie,visualize_outlierscore,visualize_distribution
from pyodds.utils.utilities import str2bool
from pyodds.automl.cash import Cash
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.simplefilter("ignore", UserWarning)
logging.disable(logging.WARNING)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Anomaly Detection Platform Settings")
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--user', default='root')
    parser.add_argument('--random_seed',default=42, type=int)
    parser.add_argument('--database',default='db')
    parser.add_argument('--table',default='t')
    parser.add_argument('--time_stamp',default=True,const=True,type=str2bool,nargs='?')
    parser.add_argument('--visualize_distribution',default=True,const=True,type=str2bool,nargs='?')
    parser.add_argument('--algorithm',default='dagmm',choices=['iforest','lof','ocsvm','robustcovariance','staticautoencoder','luminol','cblof','knn','hbos','sod','pca','dagmm','autoencoder','lstm_ad','lstm_ed'])
    parser.add_argument('--contamination',default=0.05)
    parser.add_argument('--start_time',default='2019-07-20 00:00:00')
    parser.add_argument('--end_time',default='2019-08-20 00:00:00')
    parser.add_argument('--time_serie_name',default='ts')
    parser.add_argument('--ground_truth',default=True,const=True,type=str2bool,nargs='?')
    parser.add_argument('--saving_path',default='./output/img')


    args = parser.parse_args()

    #random seed setting
    rng = np.random.RandomState(args.random_seed)
    np.random.seed(args.random_seed)

    password = "taosdata" #getpass.getpass("Please input your password:")

    #connection configeration
    conn,cursor=connect_server(args.host, args.user, password)

    #read data
    print('Load dataset and table')
    start_time = time.clock()
    if args.ground_truth:
        ground_truth_whole=insert_demo_data(conn,cursor,args.database,args.table,args.ground_truth)
    else:
        insert_demo_data(conn,cursor,args.database,args.table,args.ground_truth)


    if args.ground_truth:

        data,ground_truth = query_data(conn,cursor,args.database,args.table,
                                   args.start_time,args.end_time,args.time_serie_name,ground_truth_whole,time_serie=args.time_stamp,ground_truth_flag=args.ground_truth)
    else:
        data = query_data(conn,cursor,args.database,args.table,
                                   args.start_time,args.end_time,args.time_serie_name,time_serie=args.time_stamp,ground_truth_flag=args.ground_truth)

    print('Loading cost: %.6f seconds' %(time.clock() - start_time))
    print('Load data successful')

    # load custom dataset:
    gt_directory = './with_gt'

    result_table = pd.DataFrame(columns=['data','Prec','Recall','F1','ROC','time','model'])

    for file in os.listdir(gt_directory):
        print(file)
        data = pd.read_csv(os.path.join(gt_directory,file))
        data['value'] = data['value'].astype('float')
        ground_truth = data['label'].values
        data.drop(['label','timestamp','Unnamed: 0'],axis=1,inplace=True)
        #print(data.columns,data.shape,ground_truth.shape)

        #algorithm
        #print(data.head(10))
        if args.ground_truth:
            alg_selector = Cash(data, ground_truth)
        else:
            alg_selector = Cash(data, None)


        clf , results = alg_selector.model_selector(max_evals=50)

        # num_samples = data.shape[0]
        # split = int(num_samples * 0.75)
        # train_data, test_data = data.iloc[:split], data.iloc[split:]
        # if args.ground_truth: ground_truth = ground_truth[split:]

        print('Start processing:')
        start_time = time.clock()
        clf.fit(data)
        prediction_result = clf.predict(data)
        outlierness = clf.decision_function(data)

        # clf.fit(train_data)
        # prediction_result = clf.predict(test_data)
        # outlierness = clf.decision_function(test_data)
        print('Auto ML complete')
        results += "\n\n>>> >>> >>> >>> >>> >>> >>> === >>> >>> >>> >>> >>> >>> >>>\n\nFINAL RESULT AFTER RETRAINING\n"

        if args.ground_truth:

            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                output_performance(clf, ground_truth, prediction_result,
                                   time.clock() - start_time, outlierness)
            #print(f.getvalue())
            results += f.getvalue()
            f.close()

            acc = accuracy_score(ground_truth, prediction_result)
            prec = precision_score(ground_truth, prediction_result)
            rec = recall_score(ground_truth, prediction_result)
            f1 = f1_score(ground_truth, prediction_result)
            roc = max(roc_auc_score(ground_truth, outlierness),
                                            1 - roc_auc_score(ground_truth,
                                                              outlierness))

            with open('./results/results'+str(file)+'.txt','w') as f:
                f.write(results)
            row = [file,prec,rec,f1,roc,time.clock() - start_time,str(clf)]
            result_table.loc[len(result_table)] = row

        print('Final result complete')
        # if args.visualize_distribution and args.ground_truth:
        #     if not args.time_stamp:
        #         visualize_distribution_static(data,prediction_result,outlierness,args.saving_path)
        #         visualize_distribution(data,prediction_result,outlierness,args.saving_path)
        #         visualize_outlierscore(outlierness,prediction_result,args.contamination,args.saving_path)
        #     else:
        #         visualize_distribution_time_serie(clf.ts,data,args.saving_path)
        #         visualize_outlierscore(outlierness,prediction_result,args.contamination,args.saving_path)
        # print('Visuals complete ')

    result_table.to_csv('HEY_THR_ec2.csv')
    conn.close()
