import os
import pty
import subprocess
import sys
import select
import termios
import tty
import signal
import re
from openai import OpenAI
from InquirerPy import inquirer, get_style
from prompt_toolkit.styles import Style

class DobbyCLI:
    def __init__(self, command):
        self.command = command  # Command to be executed (e.g., ssh, telnet)

    def query_llm(self, request):
        """Send the intercepted request to the LLM and get the response."""
        client = OpenAI(
            base_url='http://localhost:11434/v1',
            api_key='ollama',  # required, but unused
        )

        response = client.chat.completions.create(
            model="llama3.1",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert network engineer assistant specialized in Cisco router and switch configurations. Your job is to suggest three CLI commands that best fits the user's request based on their prompt. Be concise, precise, and only return the commands recommended. Each suggestion should be a valid CLI command and be seprated with semicolon ONLY, without any numbering or indexing. Do not provide explanations or additional context unless specifically asked, just return the commands themselves. The goal is to help network engineers quickly identify the correct command to configure or troubleshoot their devices."
                },
                {"role": "user", "content": "check the IP addresses of all interfaces"},
                {"role": "assistant", "content": "show ip interface brief;show ip interface;show running-config"},
                {"role": "user", "content": "reload the module in slot 1/0"},
                {"role": "assistant", "content": "hw-module subslot 1/0 reload;hw-module subslot 1/0 reload oir;reload"},
                {"role": "user", "content": f"{request}"}
            ]
        )

        llm_output = response.choices[0].message.content.strip()

        # Split by common separators like newline, semicolon, period, or asterisk
        potential_commands = re.split(r'[\n;*.]', llm_output)

        # Use regex to filter only valid CLI commands (alphabetics, numbers, spaces)
        valid_commands = []
        for command in potential_commands:
            command = command.strip()  # Remove leading/trailing whitespace
            if re.match(r'^[A-Za-z0-9\s\-]+$', command):  # Only allow valid characters
                valid_commands.append(command)

        # Return the first three valid CLI suggestions
        return valid_commands[:3]
    
    def prompt_user_for_selection(self, options):
        """Prompt the user to choose one of the LLM's suggestions."""
        # Define a custom style for orange and bold font
        custom_style = get_style({
            'text': 'green',
            'texts': 'fg:#ff8000 bg:black',
            "input": "#98c379",
            'questionmark': '#ff8000 bold',  # Question mark style
            'question': 'fg:#ff8000 bg:black',      # Question style
            "answered_question": '#ff8000 bold',
            'answer': 'green bold',        # User input style
            "answermark": "#e5c07b",
            'pointer': 'green bold',       # Pointer style
            'highlighted': 'green bold underline',   # Highlighted option style
            'selected': '#ff8000 bold',      # Style for selected options
            'separator': '#cc5454',          # Separator color
            'instruction': '#ff8000 bold',               # Instruction (default)
            "long_instruction": "#ff8000 bold",                      # Plain text (default)
        })
        options.append("cancel")  # Add an cancel option
        choice = inquirer.select(
            message="Choose one of the recommended CLI commands:",
            choices=options,
            style=custom_style,
            pointer="->",
            border=True,
            show_cursor=False
        ).execute()
        return choice

    def run(self):
        """Intercept and Process the Commands Entered by the User"""
        # Create a pseudo-terminal
        # Use master_fd to intercept terminal output
        master_fd, slave_fd = pty.openpty()

        # Start the SSH/Telnet process with the given command
        process = subprocess.Popen(self.command, preexec_fn=os.setsid, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, shell=True)

        # Set the terminal to raw mode
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        def handle_exit(signum, frame):
            """Handle Ctrl+C and other exits."""
            print("\r\nExiting Dobby-CLI...\r")
            if process.poll() is None:  # Check if process is still running
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Kill the SSH/telnet process
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)  # Restore terminal settings
            sys.exit(0)  # Exit the program

        # Bind SIGINT (Ctrl+C) to the handle_exit function
        signal.signal(signal.SIGINT, handle_exit)

        try:
            buffer = ""  # Buffer to accumulate the full line of user input

            while True:
                # Check if there's any data to read from the user or the terminal
                rlist, _, _ = select.select([sys.stdin, master_fd], [], [])

                # If the user has typed something
                if sys.stdin in rlist:
                    # Read multiple characters to handle paste operation correctly
                    try:
                        user_input = os.read(sys.stdin.fileno(), 1024).decode('utf-8')  # Read up to 1024 characters at once
                    except OSError:
                        continue

                    for char in user_input:
                        # Handle Ctrl+C (manually handle '\x03' for raw mode)
                        if char == '\x03':  # Ctrl+C
                            handle_exit(None, None)  # Call exit handler directly

                        # Handle backspace (delete character from the buffer)
                        if char == '\x7f':  # Backspace key
                            if buffer:
                                buffer = buffer[:-1]
                                sys.stdout.write('\b \b')
                                sys.stdout.flush()
                            continue

                        # Detect when the user starts typing "//"
                        if buffer.endswith("//"):
                            sys.stdout.write("\033[1m\033[38;5;208m")  # Start grey mode
                            sys.stdout.write('\b \b' + '\b \b')  # Delete "//"
                            sys.stdout.write("//")  # Print again in grey
                            sys.stdout.flush()

                        # Handle Enter key
                        if char == '\r': 
                            # Only write a new line if buffer is not empty
                            if buffer.strip():
                                sys.stdout.write("\r\n")

                            # Check if the user typed "//" for prompt
                            if "//" in buffer:
                                # Change text color to grey for LLM interception
                                sys.stdout.write("\033[1m\033[38;5;208m")
                                sys.stdout.flush()

                                # Split the command after the "//"
                                request = buffer.split("//", 1)[1].strip()
                                print(f"\rIntercepted command for LLM: {request}\r")
                                
                                # Send the intercepted command to the LLM
                                llm_response = self.query_llm(request)
                                print(f"LLM Response: {llm_response}\r")

                                # Use InquirerPy to display options and get the user's choice
                                selected_command = self.prompt_user_for_selection(llm_response)
                                print(f"Selected command: {selected_command}\r")

                                # Reset text color to default after LLM response
                                sys.stdout.write("\033[0m")
                                
                                if selected_command != "cancel":
                                    # Write the selected command after the router prompt and allow user to modify it
                                    sys.stdout.write("\r\nElixir_03#")  # Assuming your router prompt is 'Elixir_03#'
                                    sys.stdout.write(selected_command)  # Write the selected command to the terminal
                                    sys.stdout.flush()

                                    # Capture any user modifications to the selected_command before executing
                                    buffer = selected_command  # Initialize buffer with the selected command

                                    while True:
                                        exit_loop = False
                                        # Read user input for potential modifications to the selected command
                                        try:
                                            user_input = os.read(sys.stdin.fileno(), 1024).decode('utf-8')
                                        except OSError:
                                            continue

                                        for char in user_input:
                                            # Handle Enter key to send the command to the router
                                            if char == '\r':
                                                sys.stdout.write("\r\n")
                                                os.write(master_fd, (buffer + "\n").encode())  # Send the final command to the router
                                                sys.stdout.flush()
                                                buffer = ""  # Clear the buffer
                                                exit_loop = True
                                                break  # Exit this loop to return to the main loop

                                            # Handle backspace to allow editing
                                            if char == '\x7f':
                                                if buffer:
                                                    buffer = buffer[:-1]  # Remove the last character from buffer
                                                    sys.stdout.write('\b \b')  # Move cursor back and delete char visually
                                                    sys.stdout.flush()
                                                continue

                                            # Add the user's input to the buffer
                                            buffer += char
                                            sys.stdout.write(char)  # Echo the character to the terminal
                                            sys.stdout.flush()
                                        
                                        if exit_loop:
                                            break

                                    # Clear buffer after handling the line
                                    buffer = ""
                                    continue
                                else:
                                    buffer = ""

                            # Send the regular input (no "//") to the device
                            os.write(master_fd, (buffer + "\n").encode())
                            # Clear buffer after sending the line
                            buffer = ""
                            continue

                        buffer += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

                # If there's output from the terminal (remote device)
                if master_fd in rlist:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    sys.stdout.write(data.decode('utf-8'))
                    sys.stdout.flush()

        except SystemExit:
            # Handle cleanup if sys.exit() is called
            pass

        finally:
            # Restore terminal settings and clean up the process
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
            if process.poll() is None:  # Check if the process is still running
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Kill the process group if still running
                except ProcessLookupError:
                    pass  # Process already terminated, so we ignore the error
            process.wait()  # Ensure the process is waited on properly

# Example usage
if __name__ == "__main__":
    # Use my Elixir-03 for testing
    DobbyCLI("telnet 10.75.221.155 2013").run()
