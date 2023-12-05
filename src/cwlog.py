import sys
import time
import threading

import boto3


class CloudWatchLogsStreamDumpThread(threading.Thread):

    def __init__(self, log_group, stream, start_time, polling_freq=5, fd=sys.stdout ):

        super().__init__(daemon=True)

        self.canceled = False
        self.log_group = log_group
        self.stream = stream
        self.start_time = start_time
        self.polling_freq = polling_freq
        self.fd = fd

        print( "CloudWatchLogsStreamDumpThread", [log_group, stream, start_time, polling_freq, fd] )

    def run(self):

        logs_client = boto3.client("logs")

        nextToken = None
        while not self.canceled:

            params = {
                "logGroupName" : self.log_group,
                "logStreamName" : self.stream,
                "startFromHead" : True,
                "limit" : 100,
            }

            if nextToken:
                params["nextToken"] = nextToken
            else:
                params["startTime"] = self.start_time

            response = logs_client.get_log_events( **params )

            for event in response["events"]:

                if self.start_time > event["timestamp"]:
                    continue

                message = event["message"]
                message = message.replace( "\0", "\\0" )
                self.fd.write( message + "\n" )

            self.fd.flush()

            assert "nextForwardToken" in response, "nextForwardToken not found"

            if response["nextForwardToken"] != nextToken:
                nextToken = response["nextForwardToken"]
            else:
                for i in range( int(self.polling_freq / 0.1) ):
                    if self.canceled:
                        break
                    time.sleep(0.1)

    def cancel(self):
        self.canceled = True
