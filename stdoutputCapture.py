import sys
import io
#import queue
import threading
import time

class StdOutputCaptureThread(threading.Thread):
    def __init__(self, output_func):
        super().__init__()
        self.output_func = output_func
        self.stdout_capture = io.StringIO()
        self.stderr_capture = io.StringIO()
        #self.output_queue = queue.Queue()
        self.stop_event = threading.Event()

        # Redirect stdout and stderr to the StringIO objects
        sys.stdout = self.stdout_capture
        sys.stderr = self.stderr_capture

    def run(self):
        while not self.stop_event.is_set():
            # Get the content of stdout and stderr
            stdout_content = self.stdout_capture.getvalue()
            stderr_content = self.stderr_capture.getvalue()

            # Check if there are new outputs
            if stdout_content:
                # self.output_queue.put(("stdout", stdout_content))
                self.output_func("stdout", stdout_content)
                # Clear the captured stdout
                self.stdout_capture.truncate(0)
                self.stdout_capture.seek(0)
            if stderr_content:
                #self.output_queue.put(("stderr", stderr_content))
                self.output_func("stderr", stderr_content)
                # Clear the captured stderr
                self.stderr_capture.truncate(0)
                self.stderr_capture.seek(0)

            # Sleep briefly before checking again
            time.sleep(0.1)

    def stop(self):
        self.stop_event.set()
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

'''
'# Example usage:
# Create and start the output capture thread
output_thread = StdOutputCaptureThread()
output_thread.start()

# Simulate some output
print("This is a test message to stdout")
sys.stderr.write("This is a test message to stderr\n")

# Read output from the queue
while not output_thread.output_queue.empty():
    source, content = output_thread.output_queue.get()
    print(f"Captured from {source}: {content}")

# Stop the output capture thread
output_thread.stop()
output_thread.join()
'''