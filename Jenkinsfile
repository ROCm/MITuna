 
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
        stage("docker build") {
        agent{  label utils.rocmnode("tunatest") }
        steps {
            script {
            utils.buildDockers()
            }
            }
        }
        stage("code Format") {
        agent{  label utils.rocmnode("tunatest") }
        steps {
            script {  
            utils.runFormat()
            }
            }
        }

        stage("pylint") {
        agent{  label utils.rocmnode("tunatest") }
        steps {
           script {
           utils.runLint()
           }
           }
        }
        stage("fin get solver"){
        agent{  label utils.rocmnode("tunatest") }
        steps {
            script {
            utils.finSolvers()
            }
            } 
        }
        stage("fin applicability"){
        //init_session called here
        agent{  label utils.rocmnode("tunatest") }
        steps {
            script{
            utils.finApplicability()
            }
            }
        }/*
        stage("pytest1"){
        agent{  label utils.rocmnode("tunatest") }
        steps{
            script{
            utils.pytestSuite1()
            }
            }
        }
        stage("pytest2"){
        agent{ label utils.rocmnode("tunatest") }
        steps{
            script{
            utils.pytestSuite2()
            }
            }
        }
        stage("pytest3 and Tests Coverage"){
            agent { label utils.rocmnode("tunatest") }
            steps {
                script {
                    utils.pytestSuite3AndCoverage(branch, branch_master)
                }
            }
        }*/
        stage("FinCompile"){
          parallel{
            stage("fin find compile enqueue"){
            agent{ label utils.rocmnode("tunatest") }
              steps{
                   script {
                       utils.finFindCompileEnqueue()
                    }
              }
            }
            stage("fin find compile execute"){
            agent{ label utils.rocmnode("tunatest") }
              steps{
                   sleep 10
                   script {
                       utils.finFindCompileExecute()
                    }
              }
            }
          }
        }
        stage("fin find eval"){
        agent{  label "gfx90a" }
        steps {
            script {
            utils.finFindEval()
            }
            }
        }
        stage("load jobs"){
        agent{ label utils.rocmnode("tunatest") }
        steps {
            script {
            utils.loadJobTest()
            }
            }
        }
        stage("perf compile"){
        agent{  label utils.rocmnode("tunatest") }
        steps {
            script {
            utils.perfCompile()
            }
            }
        }
        stage("perf eval gfx90a"){
        agent{  label "gfx90a" }
        steps{
            script {
            utils.perfEval()
            }
            }
        }
        stage("solver analytics test") {
        agent{  label "tunatest" }
        steps {
          script {
            utils.solverAnalyticsTest()
            }
            }
        }
        stage("cleanup"){
        agent{  label utils.rocmnode("tunatest") }
        steps {
           script {
           utils.cleanup()
           }
           }
        }
    }
    }
