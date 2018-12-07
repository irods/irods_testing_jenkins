## Prerequisites

- Docker: Make sure you have 18.06.1-ce, build e68fc7a installed on the host machine.
- Git: Make sure you have git installed on the host machine

## Setup Steps
- Clone irods_jenkins project on the host machine
- Change the directory to irods_jenkins
- Build the irods jenkins image using the command -> docker build -t irods-jenkins -f Dockerfile.jenkins .


We will use docker swarm to install/run this image. Docker swarm generally consists of multiple Docker Engines. In this setup we just have once Docker Engine which is running on the host machine. The hostmachine is the manager as well as the node. Docker Swarm is being used for it's secrets capability. The secrets generated using docker swarm will be used to secure the jenkins installation. For Docker Swarm to distribute images to it's various nodes it needs the images to be in a registry. We will create a registry and then push a tagged version of irods-jenkins image in the local registry and then deploy the stack.

### Docker Swarm Steps
- Initialize docker swarm -> docker swarm init
- Create and start a local registry -> $ docker service create --name registry --publish published=5000,target=5000 registry:2
- Tag the irods-jenkins image sho that it points to your local registry -> docker tag irods-jenkins localhost:5000/irods-jenkins
- Push it to the local registry/repo -> docker push localhost:5000/irds-jenkins
- To verify if the image was pushed to the registry use this command -> curl -X GET http://localhost:5000/v2/_catalog
- Before deploying the stack let's create the secrets.For security reasons please use different username and password on the production systems
     - echo "admin" | docker secret create jenkins-user -
     - echo "admin" | docker secret create jenkins-pass -
- To run/deploy the image run this command -> docker stack deploy -c irods_jenkins.yml irods-jenkins
- Jenkins can be accessed via the url http://localhost:8081

### Setting up the First Job
- First create global parameters needed to run the jobs
    - Click on Manage Jenkins -> Configure System 
    - Under Global Properties select Environment variables and a parameter with name GLOBAL_PARAMETER_DOCKER_REPO with a value /irods_docker_files and then click the Save button
    - To create a new Job click on New Item. Enter the name as test_irods_build, select Pipeline and press the OK button
    - In the pipe line section copy paste the following

node {
     stage('Docker Build') {
         def ub16_dockerfile_dir = env.GLOBAL_PARAMETER_DOCKER_REPO + '/Ubuntu_16'
         dir(ub16_dockerfile_dir) {
            sh 'docker build -t irods_ubuntu16 .'
         }
     }
}


        

