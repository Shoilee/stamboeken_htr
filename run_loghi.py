import os
import shutil
import time
import subprocess

# Define paths
source_folder = 'stamboek_906'  # Folder where the images are initially located
destination_folder = 'image_samples'  # Folder where the image will be moved
bash_script = 'scripts/inference-pipeline.sh'  # Path to your bash script


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
        os.chdir("loghi")
        subprocess.Popen(['%s %s' %(bash_script, os.path.join("..", destination_folder))], shell=True)
        # TODO: Doesn't work; says "the input device is not a TTY"
        print(f"Successfully ran bash script: {bash_script}")
        os.chdir("../")
    except subprocess.CalledProcessError as e:
        print(f"Error running bash script: {e}")


# Function to delete the image
def delete_image(image_name):
    image_path = os.path.join(destination_folder, image_name)
    if os.path.exists(image_path):
        os.remove(image_path)
        print(f"Deleted {image_name} from {destination_folder}")
    else:
        print(f"{image_name} not found in {destination_folder}")


# Main loop to repeat the steps
def main():
    base_name = 'NL-HaNA_2.10.36.22_906_'
    for i in range(6, 271):  # Loop from 0001 to 0270
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

if __name__ == '__main__':
    main()
