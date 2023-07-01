import os
import logging
import time
import configparser
import subprocess
from urllib.parse import urlparse
from gitea.api import GiteaAPI

class GitSyncer:
    """
    A class to sync a source repository with a target repository.

    Attributes:
        source_repo_url (str): The URL of the source repository.
        target_repo_url (str): The URL of the target repository.
        local_path (str): The local path where the source repository is cloned.
        wait_time (int): The time in seconds to wait between checks for new commits.
        loglevel (int): The level of logging detail.
        gitea_base_url (str): The base URL of the Gitea server.
        gitea_token (str): The access token for the Gitea API.
        last_commit_sha (str): The SHA of the last commit in the source repository.
    """

    def __init__(self, config):
        """
        Initializes the GitSyncer with a configuration.

        Args:
            config (ConfigParser): The configuration.
        """

        self.source_repo_url = config['REPOSITORIES']['Source']
        self.target_repo_url = config['REPOSITORIES']['Target']
        self.local_path = config['GENERAL']['LocalPath']
        self.wait_time = int(config['GENERAL']['WaitTime'])

        self.loglevel = getattr(logging, config['GENERAL']['LogLevel'].upper(), logging.INFO)
        logging.basicConfig(filename='git_syncer.log', level=self.loglevel)

        self.gitea_base_url = config['GITEA']['BaseURL']
        self.gitea_token = config['GITEA']['Token']
        self.target_owner = config['GITEA']['Owner']
        self.target_repo = config['GITEA']['Repository']

        self.last_commit_sha = None
        self.target_api = GiteaAPI(self.gitea_base_url, self.gitea_token)

    def _ensure_target_repository_exists(self, target_owner: str, target_repo: str, source_repo_data: dict):
        """
        Ensure that the target repository exists. If it doesn't, create it.

        Args:
            target_owner (str): The owner of the target repository.
            target_repo (str): The name of the target repository.
            source_repo_data (dict): Data from the source repository.

        Raises:
            HTTPError: If an error occurs during the API requests.
        """
        try:
            self.target_api.get_repository(target_owner, target_repo)
        except HTTPError as e:
            if e.response.status_code == 404:
                self.target_api.create_repository(
                    name=target_repo,
                    description=source_repo_data.get('description', ''),
                    private=source_repo_data.get('private', True)
                )
            else:
                raise e

    def get_source_latest_commit_sha(self):
        """
        Get the SHA of the latest commit in the source repository.

        Returns:
            str: The SHA of the latest commit.
        """
        result = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.local_path)
        return result.strip()

    def clone_source(self):
        """
        Clone the source repository to the local path.
        """
        logging.info("Starting the cloning process from the source repository...")
        subprocess.check_call(['git', 'clone', self.source_repo_url, self.local_path])

    def pull_source(self):
        """
        Pull the latest changes from the source repository.
        """
        logging.info("Starting the pull process from the source repository...")
        subprocess.check_call(['git', 'pull'], cwd=self.local_path)

    def push_target(self):
        """
        Push the cloned source repository to the target repository.
        """
        logging.info("Starting the push process to the target repository...")
        subprocess.check_call(['git', 'remote', 'add', 'target', self.target_repo_url], cwd=self.local_path)
        subprocess.check_call(['git', 'push', '-u', 'target', 'main'], cwd=self.local_path)

    def get_target_pull_requests(self):
        """
        Get the list of pull requests from the target repository.

        Returns:
            list: The list of pull requests.
        """
        logging.info("Getting the list of pull requests from the target repository...")

        # Parse the target repository URL
        parsed_url = urlparse(self.target_repo_url)
        path_parts = parsed_url.path.strip("/").split("/")
        owner = path_parts[0]
        repo = path_parts[1].rstrip('.git')

        pr_list = self.target_api.get_pull_requests(owner, repo)

        return pr_list

    def check_for_new_commit(self):
        """
        Check if there is a new commit in the source repository.
        If a new commit is detected, the handle_new_commit method is called.
        After checking, the source repository is pulled to update the local copy.
        """
        self._ensure_target_repository_exists
        self.pull_source()
        current_commit_sha = self.get_source_latest_commit_sha()
        if current_commit_sha != self.last_commit_sha:
            self.handle_new_commit(current_commit_sha)
        else:
            logging.info("No new commits detected.")
        self.last_commit_sha = current_commit_sha

    def handle_new_commit(self, commit_sha: str):
        """
        Handle the process when a new commit is detected.
        It gets the list of pull requests from the target repository,
        checks if a pull request for the new commit already exists,
        if not - it creates a new branch in the target repository,
        pushes the new commit to the created branch, and
        creates a new pull request.

        Args:
            commit_sha (str): The SHA of the new commit.
        """
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
        """
        Check if a pull request for the given commit SHA already exists.

        Args:
            commit_sha (str): The SHA of the commit to check.
            pr_list (list): The list of pull requests.

        Returns:
            bool: True if a pull request for the commit exists, False otherwise.
        """
        for pr in pr_list:
            if pr['title'] == commit_sha:
                return True
        return False

    def create_branch_in_target(self, branch_name: str):
        """
        Create a new branch in the target repository.

        Args:
            branch_name (str): The name of the new branch.
        """
        # Set the path of the local repository
        local_repo_path = self.local_path

        # Create a new branch
        subprocess.check_call(['git', 'branch', branch_name], cwd=local_repo_path)

        # Switch to the new branch
        subprocess.check_call(['git', 'checkout', branch_name], cwd=local_repo_path)

    def push_to_target_branch(self, branch_name: str):
        """
        Push the new commit to the created branch in the target repository.

        Args:
            branch_name (str): The name of the branch to push the commit to.
        """
        # Set the path of the local repository
        local_repo_path = self.local_path

        # Push the new branch to the remote repository
        subprocess.check_call(['git', 'push', '-u', 'otc_gitea', branch_name], cwd=local_repo_path)

    def create_pr_in_target(self, branch_name: str):
        """
        Create a new pull request in the target repository.

        Args:
            branch_name (str): The name of the branch to create a pull request for.
        """
        # Define the owner, repo, and base branch.
        # You might need to replace these with the appropriate variables/values depending on your setup.
        owner = self.target_owner
        repo = self.target_repo
        base = 'main'  # or whichever branch you want to merge into

        # Define the title and body of the PR.
        title = f'Pull request for branch {branch_name}'
        body = 'This is an automated pull request.'

        # Call the create_pull_request method.
        return self.target_api.create_pull_request(owner, repo, base, branch_name, title, body)

    def get_target_repository(self, owner: str, repo_name: str, auto_create: bool = False):
        """
        Get information about the target repository.

        Args:
            owner (str): The owner of the repository.
            repo_name (str): The name of the repository.
            auto_create (bool, optional): Whether to automatically create the repository if it doesn't exist.

        Returns:
            dict: Information about the repository.
        """
        try:
            repo = self.target_api.get_repository(owner, repo_name)
            logging.info(f"Accessing repository: {repo['full_name']}")
            logging.info(f"Repository URL: {repo['html_url']}")
            logging.info(f"Owner: {repo['owner']['login']}")
            logging.info(f"Created at: {repo['created_at']}")
            logging.info(f"Updated at: {repo['updated_at']}")
            return repo
        except requests.HTTPError as e:
            if e.response.status_code == 404 and auto_create:
                print(f"Repository {owner}/{repo_name} not found on target, creating...")
                self.target_api.create_repository(repo_name, f"Auto-created by GitSyncer", False, auto_init=False)
                repo = self.target_api.get_repository(owner, repo_name)
                logging.info(f"Accessing newly created repository: {repo['full_name']}")
                logging.info(f"Repository URL: {repo['html_url']}")
                logging.info(f"Owner: {repo['owner']['login']}")
                logging.info(f"Created at: {repo['created_at']}")
                logging.info(f"Updated at: {repo['updated_at']}")
                return repo
            else:
                raise e

    def sync_source_to_target(self, owner: str, repo: str):
        """
        Sync the source repository with the target repository.

        Args:
            owner (str): The owner of the target repository.
            repo (str): The name of the target repository.
        """

        # Set the URL of the target repository
        # Set the path of the local repository
        local_repo_path = self.local_path

        # Remove if exists
        target_name = "otc_gitea"
        clone_url = self.target_api.get_repository(owner, repo)['clone_url']
        target_url = clone_url.replace("http://", f"http://{self.gitea_token}@")

        try:
            subprocess.check_call(['git', 'remote', 'get-url', target_name], cwd=local_repo_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # If the above command did not raise an error, the remote exists and we can remove it
            subprocess.check_call(['git', 'remote', 'remove', target_name], cwd=local_repo_path)
        except subprocess.CalledProcessError:
            # The remote does not exist, we can safely ignore this error
            pass

        # Add a new remote named 'otc_gitea' pointing to the target repository
        subprocess.check_call(['git', 'remote', 'add', target_name, f"{target_url}"], cwd=local_repo_path)

        # Push the changes to the new remote 'otc_gitea'
        subprocess.check_call(['git', 'push', target_name, 'main'], cwd=local_repo_path)

    def run(self):
        """
        Start the syncing process and keep it running until stopped.
        """
        if not os.path.exists(self.local_path):
            self.clone_source()

        self.pull_source()
        self.last_commit_sha = self.get_source_latest_commit_sha()

        self.get_target_repository(self.target_owner, self.target_repo, auto_create=True)

        try:
            commits = self.target_api.get_commits(self.target_owner, self.target_repo)

            if not commits:
                print(f"Target repository {self.target_owner}/{self.target_repo} is empty. Syncing with source repository...")
                # Here, perform the actions to sync the source repo with the target
                # This could be done using your own functions
                #self.sync_source_to_target(owner, repo)
        except requests.HTTPError as e:
            # Catch HTTP 409 error indicating the repository is empty
            if e.response.status_code == 409 and 'Git Repository is empty.' in e.response.text:
                print(f"Target repository {self.target_owner}/{self.target_repo} is empty. Syncing with source repository...")
                # Here, perform the actions to sync the source repo with the target
                self.sync_source_to_target(self.target_owner, self.target_repo)
                time.sleep(10)
                commits = self.target_api.get_commits(self.target_owner, self.target_repo)
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
    config.read('config.ini')
    syncer = GitSyncer(config)
    syncer.run()
