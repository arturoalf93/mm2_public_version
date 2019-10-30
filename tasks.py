#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 10:35:31 2019

@author: arodriguez
"""

# https://github.com/plotly/dash-redis-celery-periodic-updates
# https://github.com/plotly/dash-redis-demo

import datetime
import json
import os
import pandas as pd
import plotly
import redis
import mysql.connector
from mysql.connector import Error

from celery import Celery
from celery.schedules import crontab
import yagmail


################################ ENVIRONMENT VARIABLES ################################

REDIS_HASH_NAME = '******'
receiver = "******@******.com"
yag = yagmail.SMTP(user="*******@gmail.com", password="*******")

on_heroku = os.environ.get("ON_HEROKU", 0)

if on_heroku:
    celery_app = Celery("Celery App", broker=os.environ.get("REDIS_URL")) 
    redis_instance = redis.StrictRedis.from_url(os.environ.get("REDIS_URL"))
    
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    host = os.environ["DB_HOST"]
    database = os.environ["DB_DATABASE"]
    port = os.environ["DB_PORT"]

else:

    celery_app = Celery("Celery App", broker='redis://127.0.0.1:6379')
    redis_instance = redis.StrictRedis.from_url('redis://127.0.0.1:6379')
    
    user = os.environ.get("DB_USER", '*******')
    password = os.environ.get("DB_PASSWORD", '******')
    host = os.environ.get("DB_HOST",'******')
    database = os.environ.get("DB_DATABASE",'******')
    port = os.environ.get("DB_PORT",'******')


########################################################################################


# disable UTC so that Celery can use local time
celery_app.conf.enable_utc = False


###################################### FUNCTIONS ######################################

def next_time(hour, minute, minutes_increment):
    minute = minute + minutes_increment
    if minute >= 60:
        minute -= 60
        hour += 1
        if hour == 24:
            hour = 0
    return hour, minute
    
########################################################################################


hour_now = datetime.datetime.now().hour
minute_now = datetime.datetime.now().minute

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    print("----> setup_periodic_tasks")
    hour, minute = next_time(hour_now, minute_now, 1)
    
    sender.add_periodic_task ( crontab(hour=hour, minute=minute), update_data.s(0), name="-->Initial data pull when deploying", expires = 10 )
    sender.add_periodic_task ( crontab(hour=20, minute=30), update_data.s(1), name="-->Update data" )


@celery_app.task
def update_data(update_type=1): # update_data actually first flushes the db and then downloads all the data again.
    # In practice, this function might be making calls to databases,
    # performing computations, etc
    
    if update_type == 0:
        update_text = 'Initial (deploy) update at ' + str(datetime.datetime.now()) + os.environ.get('TZ', ' no time zone found (Localhost)')
        print('---> enters in initial update')
    elif update_type == 1:
        print('---> enters in automatic update')
        update_text = 'Automatic update at ' + str(datetime.datetime.now()) + os.environ.get('TZ', ' no time zone found (Localhost)')
    elif update_type == 2:
        print('---> enters in manual update')
        update_text = 'Manual update at ' + str(datetime.datetime.now()) + ' ' + os.environ.get('TZ', ' no time zone found (Localhost)')
        
    try:  
        connection = mysql.connector.connect( user=user, password=password, host=host, database=database, port=port)

        cursor = connection.cursor()
        print('---> before calling export', datetime.datetime.now())
        cursor.callproc('export')
        print('---> procedure finished ', datetime.datetime.now())
        
        column_names = []
        for stored_result in cursor.stored_results():
            result = stored_result.fetchall()
            for column in stored_result.description:
                column_names.append(column[0])
                
        df = pd.DataFrame(result, columns = column_names)
        cursor.close()
        
        cursor = connection.cursor()
        cursor.callproc('metals_and_sr_conversions')
        column_names = []
        for stored_result in cursor.stored_results():
            result = stored_result.fetchall()
            for column in stored_result.description:
                column_names.append(column[0])
        metals_df = pd.DataFrame(result, columns = column_names)
        cursor.close()    
        
        connection.close()

    except Error as error:
        print("--->Something failed during DB connection: {}".format(error))
        
    df = df.rename(columns={"type": "Type"})
    df.drop_duplicates(keep='first',inplace=True)
    df['collectionTime'] = pd.to_datetime(df['collectionTime'], format='%Y-%m-%d')
    
    df_uniques = df[['Type','country','form']].drop_duplicates()
    
    try:
        last_body = redis_instance.hget(REDIS_HASH_NAME, "LAST_BODY").decode("utf-8")
    except:
        last_body = None
    print('---> last_body: ', last_body)
    
    #Flush redis
    redis_instance.flushdb()
    
    # Save the timestamp that the dataframe was updated
    redis_instance.hset( REDIS_HASH_NAME, "DATE_UPDATED", update_text )
    
    # Save the dataframe in redis so that the Dash app, running on a separate # process, can read it
    redis_instance.hset( REDIS_HASH_NAME, "METALS_DF", json.dumps( metals_df.to_dict(),cls=plotly.utils.PlotlyJSONEncoder,),)
        
    
    redis_instance.hset( REDIS_HASH_NAME, 'df_uniques', json.dumps( df_uniques.to_dict(), cls=plotly.utils.PlotlyJSONEncoder,),)
    
    dfs = {}
    
    body = 'Support / Resistance alerts report (prices in USD):\n\n'
    n_alerts = 0
    
    print('---> starting dfs', datetime.datetime.now())
    for index, row in df_uniques.iterrows():
        Type = row['Type']
        country = row['country']
        form = row['form']
        
        sub_df = Type + '-' + country + '-' + form
        dfs[sub_df] = df[(df['Type']==row['Type']) &  (df['country'] == row['country']) & (df['form'] == row['form'])]
        redis_instance.hset( REDIS_HASH_NAME, sub_df, json.dumps( dfs[sub_df].to_dict(), cls=plotly.utils.PlotlyJSONEncoder,),)
        
        max_date = dfs[sub_df]['collectionTime'].max()
        current_price = dfs[sub_df][dfs[sub_df]['collectionTime'] == max_date]['USD'].tolist()[0]
        
        metals_df_filtered = metals_df[(metals_df['Type']==Type) &  (metals_df['country'] ==country) & (metals_df['form']== form)]
        lt_support = metals_df_filtered['lt_support_USD'].tolist()[0]
        lt_resistance = metals_df_filtered['lt_resistance_USD'].tolist()[0]
        st_support = metals_df_filtered['st_support_USD'].tolist()[0]
        st_resistance = metals_df_filtered['st_resistance_USD'].tolist()[0]
        
        lt_current_price_position = (current_price - lt_support)/(lt_resistance - lt_support)
        st_current_price_position = (current_price - st_support)/(st_resistance - st_support)
        
        if lt_current_price_position <= 0.1 or lt_current_price_position >= 0.9:
            n_alerts += 1
            body = body + '<b>' + str(n_alerts) +'. ' + Type + '-' + country + '-' + form + ':</b>\n&nbsp;&nbsp;&nbsp;&nbsp;lt_support: ' + str(lt_support) + '\n&nbsp;&nbsp;&nbsp;&nbsp;lt_resistance: ' + str(lt_resistance) + '\n&nbsp;&nbsp;&nbsp;&nbsp;current_price: ' + str(current_price) + ', as of ' + str(max_date) + '\n&nbsp;&nbsp;&nbsp;&nbsp;lt_current_price_position: ' + str(round(lt_current_price_position*100 ,2)) + '%\n\n'    
        if st_current_price_position <= 0.1 or st_current_price_position >= 0.9:
            n_alerts += 1
            body = body + '<b>' + str(n_alerts) +'. ' + Type + '-' + country + '-' + form + ':</b>\n&nbsp;&nbsp;&nbsp;&nbsp;st_support: ' + str(st_support) + '\n&nbsp;&nbsp;&nbsp;&nbsp;st_resistance: ' + str(st_resistance) + '\n&nbsp;&nbsp;&nbsp;&nbsp;current_price: ' + str(current_price) + ', as of ' + str(max_date) + '\n&nbsp;&nbsp;&nbsp;&nbsp;st_current_price_position: ' + str(round(st_current_price_position*100 ,2)) + '%\n\n'
    print('---> dfs finished', datetime.datetime.now())
    
    if  body != last_body:
        redis_instance.hset( REDIS_HASH_NAME, "LAST_BODY", body )
        if n_alerts == 1:
            subject = 'Support/Resitance - ' + str(n_alerts) + ' alert - ' + str(datetime.datetime.now())
        else:
            subject = 'Support/Resitance - ' + str(n_alerts) + ' alerts - ' + str(datetime.datetime.now())
        yag.send( to=receiver, subject=subject, contents=body )
        print('--->mail sent to: ', receiver)
        print('--->body: ', body)

