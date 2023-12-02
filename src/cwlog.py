import sys
import time
import threading

import boto3


def monitor_cw_log( log_group_name, log_stream_name, start_time, polling_freq=5, region=None ):

    print("")

    class CloudWatchLogsPrintingThread(threading.Thread):

        def __init__(self):
            super().__init__(daemon=True)
            self.canceled = False

        def run(self):

            logs_client = boto3.client( "logs", region_name=region )

            nextToken = None
            while not self.canceled:

                params = {
                    "logGroupName" : log_group_name,
                    "logStreamName" : log_stream_name,
                    "startFromHead" : True,
                    "limit" : 100,
                }

                if nextToken:
                    params["nextToken"] = nextToken
                else:
                    params["startTime"] = start_time

                response = logs_client.get_log_events( **params )

                for event in response["events"]:

                    if start_time > event["timestamp"]:
                        continue

                    message = event["message"]
                    message = message.replace( "\0", "\\0" )
                    print( message )

                assert "nextForwardToken" in response, "nextForwardToken not found"

                if response["nextForwardToken"] != nextToken:
                    nextToken = response["nextForwardToken"]
                else:
                    for i in range( int(polling_freq / 0.1) ):
                        if self.canceled:
                            break
                        time.sleep(0.1)

    th = CloudWatchLogsPrintingThread()
    th.start()
    
    while True:
        c = sys.stdin.read(1)
        if c in ("q","Q"):
            th.canceled = True
            th.join()
            break

    print("")


monitor_cw_log(
    log_group_name = "/aws/sagemaker/Clusters/SampleBase5/ycml5hterpsx",
    log_stream_name = "LifecycleConfig/controller-machine/i-0a88597a09d8a6552",
    start_time = int( ( time.time() - 10 * 24* 60 * 60 ) * 1000 ) # 10 days
)