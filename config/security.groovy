#!groovy

import jenkins.model.Jenkins
import hudson.slaves.EnvironmentVariablesNodeProperty
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.GlobalMatrixAuthorizationStrategy
import hudson.security.csrf.DefaultCrumbIssuer
import jenkins.security.s2m.AdminWhitelistRule

def hudsonRealm = new HudsonPrivateSecurityRealm(false)
def adminUsername = new File("/run/secrets/jenkins-user").text.trim()
def adminPassword = new File("/run/secrets/jenkins-pass").text.trim()
hudsonRealm.createAccount(adminUsername, adminPassword)

def instance = Jenkins.getInstance()
instance.setSecurityRealm(hudsonRealm)

def strategy = new GlobalMatrixAuthorizationStrategy()

//Setting Admin Permissions
strategy.add(Jenkins.ADMINISTER, adminUsername)
instance.setAuthorizationStrategy(strategy)
instance.save()

//Prevent Cross Site Request Forgery exploits
Jenkins.getInstance().setCrumbIssuer(new DefaultCrumbIssuer(true))

//Disable Slave to Master Access Control
Jenkins.getInstance().getInjector().getInstance(AdminWhitelistRule.class).setMasterKillSwitch(false)

//Disable CLI over Remoting
Jenkins.getInstance().getDescriptor("jenkins.CLI").get().setEnabled(false)
