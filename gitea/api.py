import requests
from typing import Optional,Dict,List

class GiteaAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token
        self.headers = {
            'Authorization': f'token {self.token}',
            'Content-Type': 'application/json'
        }

    def get_pull_requests(self, owner, repo, state=None, sort=None, milestone=None, labels=None, page=None, limit=None):
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            'state': state,
            'sort': sort,
            'milestone': milestone,
            'labels': labels,
            'page': page,
            'limit': limit
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()  # Throws an error if the request failed
        return response.json()

    def get_repository(self, owner: str, repo: str) -> Dict:
        """
        Gets the details of a repository.

        Args:
            owner (str): The owner of the repository.
            repo (str): The name of the repository.

        Returns:
            dict: The details of the repository.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()  # Throws an error if the request failed
        return response.json()

    def create_repository(self,
                          name: str,
                          description: Optional[str] = '',
                          private: Optional[bool] = True,
                          auto_init: Optional[bool] = True,
                          gitignores: Optional[str] = '',
                          issue_labels: Optional[str] = '',
                          license: Optional[str] = '',
                          readme: Optional[str] = '',
                          template: Optional[bool] = True,
                          default_branch: Optional[str] = 'main',
                          trust_model: Optional[str] = 'default') -> Dict:

        """
        Create a new repository.

        Args:
            name (str): The name of the repository.
            description (str, optional): The description of the repository.
            private (bool, optional): Whether the repository should be private.
            auto_init (bool, optional): Whether the repository should be auto initialized.
            gitignores (str, optional): .gitignore template.
            issue_labels (str, optional): Issue labels.
            license (str, optional): License.
            readme (str, optional): Readme.
            template (bool, optional): Whether the repository is a template.
            default_branch (str, optional): The default branch.
            trust_model (str, optional): The trust model.

        Returns:
            dict: The created repository as a dictionary.
        """

        url = f"{self.base_url}/user/repos"

        payload = {
            "auto_init": auto_init,
            "default_branch": default_branch,
            "description": description,
            "gitignores": gitignores,
            "issue_labels": issue_labels,
            "license": license,
            "name": name,
            "private": private,
            "readme": readme,
            "template": template,
            "trust_model": trust_model
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()  # Throws an error if the request failed

        return response.json()

    def get_branches(self, owner: str, repo: str, page: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """
        Gets the list of branches in a repository.

        Args:
            owner (str): The owner of the repository.
            repo (str): The name of the repository.
            page (int, optional): Page number of results to return (1-based).
            limit (int, optional): Page size of results.

        Returns:
            list: The list of branches in the repository. Each branch is represented as a dictionary.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/branches"
        params = {
            'page': page,
            'limit': limit
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()  # Throws an error if the request failed
        return response.json()

    def get_commits(self, owner: str, repo: str, sha: str = None, path: str = None, stat: bool = True, page: int = 1, limit: int = None):
        params = {
            "sha": sha,
            "path": path,
            "stat": str(stat).lower(),
            "page": page,
            "limit": limit
        }

        # Filter out None values from params
        params = {k: v for k, v in params.items() if v is not None}

        response = requests.get(f"{self.base_url}/repos/{owner}/{repo}/commits", headers=self.headers, params=params)

        # Raise an exception if the GET request was unsuccessful
        response.raise_for_status()

        return response.json()

    def create_pull_request(self, owner: str, repo: str, base: str, head: str, title: str, body: str = "", assignee: str = None, assignees: list = None, labels: list = None, milestone: int = None, due_date: str = None):
        """
        Create a pull request.

        Args:
            owner (str): owner of the repo
            repo (str): name of the repo
            base (str): branch (or git ref) you want your changes pulled into
            head (str): branch (or git ref) where your changes are implemented
            title (str): title of the pull request
            body (str): body text of the pull request
            assignee (str): username of the user that this pull request should be assigned to
            assignees (list): list of usernames that this pull request should be assigned to
            labels (list): list of label IDs to associate with this pull request
            milestone (int): ID of the milestone to associate this pull request with
            due_date (str): ISO8601 formatted due date for this pull request

        Returns:
            dict: Response from Gitea API.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"

        data = {
            "assignee": assignee,
            "assignees": assignees,
            "base": base,
            "body": body,
            "due_date": due_date,
            "head": head,
            "labels": labels,
            "milestone": milestone,
            "title": title
        }

        # Filter out None values
        data = {k: v for k, v in data.items() if v is not None}

        response = requests.post(url, headers=self.headers, json=data)
        print(response)

        # Raise an exception if the request was unsuccessful
        if not response.ok:
            response.raise_for_status()

        return response.json()
