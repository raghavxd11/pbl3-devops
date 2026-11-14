// Runs on every Jenkins start: creates/updates the 3 PBL-III pipeline jobs.
import jenkins.model.Jenkins
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition
import hudson.plugins.git.GitSCM
import hudson.plugins.git.BranchSpec

def repo = System.getenv('GIT_REPO_URL')
def branch = System.getenv('GIT_BRANCH') ?: 'main'

if (!repo) {
    println '[pbl] GIT_REPO_URL not set - skipping job creation'
    return
}

def jenkins = Jenkins.get()
def jobs = [
    ['task1-cicd-k8s',   'Jenkinsfile.task1', 'Task 1: CI/CD pipeline deploying the Dockerized app to Kubernetes'],
    ['task2-blue-green', 'Jenkinsfile.task2', 'Task 2: Automated blue-green deployment'],
    ['task3-devsecops',  'Jenkinsfile.task3', 'Task 3: DevSecOps pipeline for the healthcare Patient Records API'],
]

jobs.each { item ->
    def name = item[0]; def path = item[1]; def desc = item[2]
    def job = jenkins.getItem(name)
    if (job == null) {
        job = jenkins.createProject(WorkflowJob, name)
    }
    def scm = new GitSCM(
        GitSCM.createRepoList(repo, null),
        [new BranchSpec("*/${branch}")],
        null, null, []
    )
    def definition = new CpsScmFlowDefinition(scm, path)
    definition.setLightweight(true)
    job.setDefinition(definition)
    job.setDescription(desc)
    job.save()
    println "[pbl] job ready: ${name} -> ${path}"
}
jenkins.save()
