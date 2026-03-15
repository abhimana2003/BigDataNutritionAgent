# EECS E6895: Advanced Big Data and AI Midterm Project

**Nutritionist 1 Group:**

- Anjali Bhimanadham — apb2192  
- Mahsa Mohajeri — mm6859  
- Daniyah Taimur — drt2145

## Project Description
We developed a Nutrition AI system that  generates personalized meal plans, recipes, and grocery lists based on one’s:
- Age, weight, height, gender
- Goals (weight loss, maintenance, high protein) 
- Dietary preferences, allergies, medical conditions
- Budget
- Cooking time


## Setup
1. Create a Groq API key: https://console.groq.com/keys

2. Open terminal (command line) and copy the example env file using the following command

    ```bash
    cp .env.example .env
    ```

3. Open the env file just created. Add your key where it says

    ```env
    GROQ_API_KEY=your_groq_key_here
    ```

4. Run the project in the terminal 
    This installs any dependencies as well as sets up the databases and anything else needed for the system to run. It should open up the application on your browser once all of that is done. 

    ```bash
    ./run_project.sh
    ```
## Example Use Case
A user can create a profile by filling out all the information in the form. For example, they may select weight loss as their goal, vegetarian as a dietary preference, and none for allergies or medical conditions. 

The app then generates a 7 day meal plan for the user as well as a grocery list. Users can choose to like or dislike recipes so that the agent can understand what types of recipes to recommend in the future. They can also replace recipes if they just want to replace them or if the recipe doesn't fit their constraints. 

Users can also update their profiles in the "Profile Settings" tab, which will make the agent regenerate a meal plan for them based on their new constraints. 
