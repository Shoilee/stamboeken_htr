import os
import pty
import shutil
import time
import subprocess

# DEFINE PATHS
source_folder = 'data/images'  # Folder where the images are initially located
destination_folder = 'data/htr'  # Folder where the image will be moved
# bash_script = 'scripts/inference-pipeline.sh'  # Path to your bash script



# Function to copy the image
def copy_image(image_name):
    source_path = os.path.join(source_folder, image_name)
    destination_path = os.path.join(destination_folder, image_name)
    if os.path.exists(source_path):
        shutil.copy(source_path, destination_path)
        print(f"Copied {image_name} to {destination_folder}")
    else:
        print(f"{image_name} not found in {source_folder}")


# Function to run the bash script
def run_bash_script():
    try:
        # os.chdir("../")
        os.chdir("loghi")
        # TODO: Doesn't work; says "the input device is not a TTY"
        # subprocess.Popen(['%s %s' %(bash_script, os.path.join("..", destination_folder))], shell=True)

        # Create new tty
        # otherwise got error: "the input device is not a TTY"
        master_fd, slave_fd = pty.openpty()

        # Call CLI Process
        cmd = "scripts/inference-pipeline.sh " \
                  "../data/htr"

        print("[DEBUG]: {}".format(cmd))
        proc = subprocess.Popen(cmd,
                                stdin=slave_fd,
                                stderr=subprocess.STDOUT,
                                shell=True,
                                universal_newlines=True,
                                start_new_session=True)

        proc.communicate()
        print(f"Successfully ran bash script: {cmd}")
        os.chdir("../") # Change back to the original directory
        
    except subprocess.CalledProcessError as e:
        print(f"Error running bash script: {e}")
        os.chdir("../") # Change back to the original directory


# Function to delete the image
def delete_image(image_name):
    image_path = os.path.join(destination_folder, image_name)
    if os.path.exists(image_path):
        os.remove(image_path)
        os.remove(image_path+".done")
        print(f"Deleted {image_name} from {destination_folder}")
    else:
        print(f"{image_name} not found in {destination_folder}")


# Main loop to repeat the steps
def run_loghi_for_entire_folio(base_name):
    for i in range(77, 267):  # Loop from 0004 to 0266
        image_name = f"{base_name}{str(i).zfill(4)}"  # Format the counter with leading zeros
        image_name += '.jpg'  # Assuming the images are in .jpg format

        # Step 1: Copy the image
        copy_image(image_name)

        # Step 2: Run the bash script
        run_bash_script()

        # Step 3: Delete the image
        delete_image(image_name)

        # Pause for a moment before moving to the next image
        time.sleep(5)  # Adjust the sleep time as needed

def main():
    # Iterate over all files in the folder
    for filename in os.listdir(source_folder):
        # file_path = os.path.join(source_folder, filename)
        
        if filename.endswith('.jpg'):
            image_name = filename

            # Step 1: Copy the image
            copy_image(image_name)

            # Step 2: Run the bash script
            run_bash_script()

            # Step 3: Delete the image
            delete_image(image_name)

            # Pause for a moment before moving to the next image
            time.sleep(5)  # Adjust the sleep time as needed


if __name__ == '__main__':
    # run_loghi_for_entire_folio(base_name = 'NL-HaNA_2.10.36.22_906_')  # Base name for image
    main()
