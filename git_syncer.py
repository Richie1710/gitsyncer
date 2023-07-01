import os
import logging
import time
import configparser
import subprocess
import requests
from urllib.parse import urlparse
from gitea.api import GiteaAPI


class GitSyncer:
    def __init__(self, config):
        self.source_repo_url = config["REPOSITORIES"]["Source"]
        self.target_repo_url = config["REPOSITORIES"]["Target"]
        self.local_path = config["GENERAL"]["LocalPath"]
        self.wait_time = int(config["GENERAL"]["WaitTime"])
        self.loglevel = getattr(
            logging, config["GENERAL"]["LogLevel"].upper(), logging.INFO
        )
        logging.basicConfig(filename="git_syncer.log", level=self.loglevel)
        self.gitea_base_url = config["GITEA"]["BaseURL"]
        self.gitea_token = config["GITEA"]["Token"]
        self.target_owner = config["GITEA"]["Owner"]
        self.target_repo = config["GITEA"]["Repository"]
        self.last_commit_sha = None
        self.target_api = GiteaAPI(self.gitea_base_url, self.gitea_token)

    def get_source_latest_commit_sha(self):
        result = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.local_path
        )
        return result.strip()

    def clone_source(self):
        logging.info("Starting the cloning process from the source repository...")
        subprocess.check_call(["git", "clone", self.source_repo_url, self.local_path])

    def pull_source(self):
        logging.info("Starting the pull process from the source repository...")
        subprocess.check_call(["git", "pull"], cwd=self.local_path)

    def push_target(self):
        logging.info("Starting the push process to the target repository...")
        subprocess.check_call(
            ["git", "remote", "add", "target", self.target_repo_url],
            cwd=self.local_path,
        )
        subprocess.check_call(
            ["git", "push", "-u", "target", "main"], cwd=self.local_path
        )

    def get_target_pull_requests(self):
        logging.info("Getting the list of pull requests from the target repository...")
        parsed_url = urlparse(self.target_repo_url)
        path_parts = parsed_url.path.strip("/").split("/")
        owner = path_parts[0]
        repo = path_parts[1].rstrip(".git")
        pr_list = self.target_api.get_pull_requests(owner, repo)
        return pr_list

    def check_for_new_commit(self):
        self.pull_source()
        current_commit_sha = self.get_source_latest_commit_sha()
        if current_commit_sha != self.last_commit_sha:
            self.handle_new_commit(current_commit_sha)
        else:
            logging.info("No new commits detected.")
        self.last_commit_sha = current_commit_sha

    def handle_new_commit(self, commit_sha: str):
        pr_list = self.get_target_pull_requests()
        pr_exists = self.check_if_pr_exists(commit_sha, pr_list)
        if not pr_exists:
            branch_name = f"branch_{commit_sha}"
            self.create_branch_in_target(branch_name)
            self.push_to_target_branch(branch_name)
            self.create_pr_in_target(branch_name)
        else:
            logging.info("A PR for the new commit already exists, skipping.")

    def check_if_pr_exists(self, commit_sha: str, pr_list: list) -> bool:
        for pr in pr_list:
            if pr["title"] == commit_sha:
                return True
        return False

    def create_branch_in_target(self, branch_name: str):
        local_repo_path = self.local_path
        subprocess.check_call(["git", "branch", branch_name], cwd=local_repo_path)
        subprocess.check_call(["git", "checkout", branch_name], cwd=local_repo_path)

    def push_to_target_branch(self, branch_name: str):
        local_repo_path = self.local_path
        subprocess.check_call(
            ["git", "push", "-u", "otc_gitea", branch_name], cwd=local_repo_path
        )

    def create_pr_in_target(self, branch_name: str):
        owner = self.target_owner
        repo = self.target_repo
        base = "main"
        title = f"Pull request for branch {branch_name}"
        body = "This is an automated pull request."
        return self.target_api.create_pull_request(
            owner, repo, base, branch_name, title, body
        )

    def run(self):
        if not os.path.exists(self.local_path):
            self.clone_source()
        self.pull_source()
        self.last_commit_sha = self.get_source_latest_commit_sha()
        try:
            commits = self.target_api.get_commits(self.target_owner, self.target_repo)
            if not commits:
                print(
                    f"Target repository {self.target_owner}/{self.target_repo} is empty. Syncing with source repository..."
                )
                self.sync_source_to_target(self.target_owner, self.target_repo)
        except requests.HTTPError as e:
            if (
                e.response.status_code == 409
                and "Git Repository is empty." in e.response.text
            ):
                print(
                    f"Target repository {self.target_owner}/{self.target_repo} is empty. Syncing with source repository..."
                )
                self.sync_source_to_target(self.target_owner, self.target_repo)
                time.sleep(10)
                commits = self.target_api.get_commits(
                    self.target_owner, self.target_repo
                )
            else:
                raise e
        while True:
            try:
                logging.info("Beginning the synchronization process...")
                self.check_for_new_commit()
                logging.info("Synchronization completed.")
                time.sleep(self.wait_time)
            except Exception as e:
                logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")
    syncer = GitSyncer(config)
    syncer.run()
