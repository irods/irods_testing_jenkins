## Prerequisites
At least the following versions:

```
$ git --version
git version 1.9.0

$ docker --version
Docker version 18.06.1-ce, build e68fc7a
```

## Build Jenkins Image
Clone the repository, change directory, and build the docker image.

```
git clone https://github.com/irods/irods_testing_jenkins
cd irods_testing_jenkins
docker build -t irods-jenkins --build-arg arg_jenkins_output=/full/path/on/host/for/jenkins_output -f Dockerfile.jenkins .
```
Remember the path you specified for the **jenkins_output** directory. You'll need it later.

## Docker Swarm
We will use docker swarm to install/run this image. Docker swarm generally consists of multiple Docker Engines. In this setup we just have once Docker Engine which is running on the host machine. The hostmachine is the manager as well as the node. Docker Swarm is being used for its secrets capability. The secrets generated using docker swarm will be used to secure the jenkins installation. For Docker Swarm to distribute images to its various nodes it needs the images to be in a registry. We will create a registry and then push a tagged version of irods-jenkins image to the local registry and then deploy the stack.

- Initialize docker swarm
    ```
    docker swarm init
    ```
- Create and start a local registry:
    ```
    docker service create --name registry --publish published=5000,target=5000 registry:2
    ```
- Tag the irods-jenkins image so that it points to the local registry:
    ```
    docker tag irods-jenkins localhost:5000/irods-jenkins
    ```
- Push it to the local registry:
    ```
    docker push localhost:5000/irods-jenkins
    ```
- Verify the image was pushed to the registry:
    ```
    curl -X GET http://localhost:5000/v2/_catalog
    ```
- Create the secrets. Please use a different username and password on production systems.
    ```
    echo "admin" | docker secret create jenkins-user -
    echo "admin" | docker secret create jenkins-pass -
    ```
- Update the **jenkins_output** volume mount in the **irods_jenkins.yml** file. The path must match the path you provided during the build. For example:
    ```
    - /full/path/on/host/for/jenkins_output:/jenkins_output:rw
    ```
- Deploy the image:
    ```
    docker stack deploy -c irods_jenkins.yml irods-jenkins
    ```
- Connect to the running Jenkins instance and login with admin/password:
    http://localhost:8081
- Stop Jenkins
    ```
    docker service rm irods-jenkins_main
    ```
- Restart Jenkins
    ```
    docker stack deploy -c irods_jenkins.yml irods-jenkins
    ```

## Miscellaneous
If you're interested in modifying or enhancing this project, see [DEVELOPERS.md](./DEVELOPERS.md).
