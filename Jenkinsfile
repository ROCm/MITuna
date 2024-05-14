 
library "jenkins-shared@$BRANCH_NAME"

pipeline {
    agent any
    environment {
        branch =  sh(script: "echo ${scm.branches[0].name} | sed 's/[^a-zA-Z0-9]/_/g' ", returnStdout: true).trim()
        branch_id = "${branch}_${BUILD_ID}"
        branch_master = "develop"
        db_name = "${TUNA_DB_NAME}_${branch}_${BUILD_ID}"
        docker_args = '--privileged --device=/dev/kfd --device /dev/dri:/dev/dri:rw --volume /dev/dri:/dev/dri:rw -v /var/lib/docker/:/var/lib/docker --group-add video'
        db_host = "${CI_DB_HOSTNAME}" 
        db_user = "${DB_USER_NAME}"
        db_password = "${DB_USER_PASSWORD}"
        pipeline_user = "${PIPELINE_USER}"
        pipeline_pwd = "${PIPELINE_PWD}"
        arch = 'gfx90a'
        num_cu = '104'
        machine_ip = "${machine_ip}"
        machine_local_ip =  "${machine_local_ip}"
        username = "${username}"
        pwd = "${pwd}"
        port = "${port}"
        TUNA_ROCM_VERSION = '4.5'
        docker_registry = "${DOCKER_REGISTRY}"
    } 
    stages {
        stage("TEST LOOP") {
        agent{  label utils.rocmnode("tunatest") }
            steps {
              script {
                utils.testLoop()
              }
          }
    }
    }
}
