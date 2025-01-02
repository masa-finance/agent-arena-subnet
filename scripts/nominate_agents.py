import requests
import json
import os
import httpx
import random
import csv

from typing import Dict, Any
from tqdm import tqdm  # Import tqdm for progress bar
from protocol.x.queue import RequestQueue
from interfaces.types import (
    RegisteredAgentRequest,
    Profile,
)


def fetch_virtual_agents():
    url = "https://api.virtuals.io/api/virtuals"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "dnt": "1",
        "origin": "https://app.virtuals.io",
        "priority": "u=1, i",
        "referer": "https://app.virtuals.io/",
        "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    params = {
        "filters[status][$in][0]": "AVAILABLE",
        "filters[status][$in][1]": "ACTIVATING",
        "filters[priority][$ne]": "-1",
        "sort[0]": "totalValueLocked:desc",
        "sort[1]": "createdAt:desc",
        "populate[0]": "image",
        "pagination[page]": "1",
        "pagination[pageSize]": "100",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


async def fetch_agents_twitter_profiles():
    agents_data = fetch_virtual_agents()
    agents = agents_data.get("data", [])

    queue = RequestQueue()
    profiles = []  # List to store profiles
    no_username_count = 0  # Counter for agents with no username
    skipped_count = 0  # Counter for agents with no socials

    # Use tqdm to create a progress bar
    for agent in tqdm(agents, desc="Fetching Twitter Profiles"):
        socials = agent.get("socials", {})

        if socials is None:
            skipped_count += 1
            continue

        username = socials.get("TWITTER") or socials.get("USER_LINKS", {}).get(
            "TWITTER"
        )
        if username and "x.com" in username:
            username = username.split("/")[-1]  # Extract the username from the URL

        if username:
            profile = await queue.excecute_request(
                request_type="profile", request_data={"username": username}
            )
            # Store both the agent and its profile
            profiles.append({"agent": agent, "profile": profile})
        else:
            no_username_count += 1  # Increment counter if no username

        await asyncio.sleep(
            random.uniform(3, 6)
        )  # Add a random sleep between 3 and 6 seconds

    print("✨🎉 Virtual Agents profile fetching completed successfully! 🎉✨")
    print(f"Number of agents with no username: {no_username_count}")
    print(f"Number of agents skipped due to no socials: {skipped_count}")
    print(f"Number of profiles fetched: {len(profiles)}")

    return profiles  # Return the list of profiles


def fetch_creator_bid_agents():
    url = "https://creator.bid/api/agents"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    params = {
        "type": "user",
        "limit": 100,
        "page": 1,
        "sortBy": "marketCap",
        "sortDirection": "desc",
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        agents = response.json().get("agents")
        return agents
    else:
        response.raise_for_status()


def fetch_agent_details(agent_id: str) -> Dict[str, Any]:
    print(f"Fetching agent {agent_id}")
    url = f"https://creator.bid/api/agents/{agent_id}"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()


def fetch_all_creator_bid_agents_details():
    agents = fetch_creator_bid_agents()
    detailed_agents = []

    for agent in tqdm(agents, desc="Fetching Agent Details"):
        agent_id = agent.get("_id")
        if agent_id:
            details = fetch_agent_details(agent_id)
            # Aggregate the base agent data with the detailed data
            aggregated_details = {"agent": agent, "details": details}
            detailed_agents.append(aggregated_details)
    return detailed_agents


async def fetch_creator_bid_agents_twitter_profiles():
    detailed_agents = fetch_all_creator_bid_agents_details()
    queue = RequestQueue()
    profiles = []  # List to store profiles
    no_username_count = 0  # Counter for agents with no username

    for agent in tqdm(detailed_agents, desc="Fetching Twitter Profiles"):
        details = agent.get("details")

        socials = details.get("socials", [])
        twitter_info = next((s for s in socials if s.get("id") == "twitter"), None)
        username = twitter_info.get("username") if twitter_info else None

        if username:
            profile = await queue.excecute_request(
                request_type="profile", request_data={"username": username}
            )
            # Store both the agent and its profile
            profiles.append({"agent": agent, "profile": profile})
        else:
            no_username_count += 1  # Increment counter if no username

        await asyncio.sleep(
            random.uniform(3, 6)
        )  # Add a random sleep between 3 and 6 seconds

    print("🎉 Finished fetching X profiles for all Creator.bid agents! 🚀")
    print(f"Number of agents with no username: {no_username_count}")
    print(f"Number of profiles fetched: {len(profiles)}")

    return profiles  # Return the list of profiles


async def upload_agent(agent_with_profile: Dict[str, Any]) -> None:
    """Upload agent data to the server.

    Args:
        agent_with_profile (Dict[str, Any]): A dictionary containing agent and profile data.
    """
    agent = agent_with_profile["agent"]
    profile = agent_with_profile["profile"]
    netuid = int(os.getenv("NETUID", "59"))

    print("Attempting to upload agent")

    # Construct the data to be uploaded
    upload_data = RegisteredAgentRequest(
        subnet_id=netuid,  # Default to 59 if not provided
        version=str(agent.get("version", 4)),  # Default to version 4 if not provided
        isActive=False,
        isNominated=True,
        nominations=0,
        marketcap=1,
        profile={
            "data": Profile(
                UserID=profile["data"].get("UserID"),
                Username=profile["data"].get("Username"),
                Avatar=profile["data"].get("Avatar"),
                Banner=profile["data"].get("Banner"),
                Biography=profile["data"].get("Biography"),
                FollowersCount=profile["data"].get("FollowersCount"),
                FollowingCount=profile["data"].get("FollowingCount"),
                LikesCount=profile["data"].get("LikesCount"),
                Name=profile["data"].get("Name"),
            )
        },
    )

    print(f"data: {upload_data}")

    # Convert to JSON
    upload_data_json = json.loads(json.dumps(upload_data, default=lambda o: o.__dict__))

    # Define the endpoint and headers
    endpoint = f"{os.getenv('API_URL', 'https://test.protocol-api.masa.ai')}/v1.0.0/subnet59/miners/register"
    headers = {"Authorization": f"Bearer {os.getenv('API_KEY')}"}

    # Make the POST request
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=upload_data_json, headers=headers)

    # Log the result
    if response.status_code == 200:
        print("Successfully uploaded agent!")
    else:
        print(
            f"Failed to upload agent, status code: {response.status_code}, message: {response.text}"
        )


def write_profiles_to_csv(
    virtuals_profiles, creatorbid_profiles, csv_file_path="agent_profiles.csv"
):
    """Write Twitter profile username and marketcap to a CSV file."""
    # Define the CSV headers
    csv_headers = ["Username", "Marketcap"]

    # Open the CSV file for writing
    with open(csv_file_path, mode="w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
        writer.writeheader()

        # Write virtuals profiles to CSV
        for profile in virtuals_profiles:
            try:
                agent = profile.get("agent")
                if agent is None:
                    continue
                username = (
                    profile.get("profile", {})
                    .get("data", {})
                    .get("Username", "unknown")
                )
                marketcap = agent.get("mcapInVirtual", "0")
                writer.writerow({"Username": username, "Marketcap": marketcap})
            except AttributeError as e:
                print(f"Skipping virtual profile due to error: {e}")

        # Write creatorbid profiles to CSV
        for profile in creatorbid_profiles:
            try:
                agent = profile.get("agent", {}).get("agent")
                if agent is None:
                    continue
                username = (
                    profile.get("profile", {})
                    .get("data", {})
                    .get("Username", "unknown")
                )
                marketcap = agent.get("marketCap", "0")
                writer.writerow({"Username": username, "Marketcap": marketcap})
            except AttributeError as e:
                print(f"Skipping creatorbid profile due to error: {e}")

    print(f"CSV file '{csv_file_path}' has been created with agent profiles.")


if __name__ == "__main__":
    import asyncio

    try:

        # Fetch Twitter profiles for creator.bid agents
        # creatorbid_profiles = asyncio.run(fetch_creator_bid_agents_twitter_profiles())

        # import csv

        # # Define the CSV file path
        # csv_file_path = "agent_profiles.csv"

        # # Combine virtuals and creatorbid profiles
        # combined_profiles = virtuals_profiles + creatorbid_profiles

        # # Define the CSV headers
        # csv_headers = [
        #     "UserID",
        #     "Username",
        #     "Avatar",
        #     "Banner",
        #     "Biography",
        #     "FollowersCount",
        #     "FollowingCount",
        #     "LikesCount",
        #     "Name",
        # ]

        # # Write the combined profiles to a CSV file
        # with open(csv_file_path, mode="w", newline="", encoding="utf-8") as csv_file:
        #     writer = csv.DictWriter(csv_file, fieldnames=csv_headers)
        #     writer.writeheader()

        #     for profile in combined_profiles:
        #         profile_data = profile.get("data", {})
        #         writer.writerow(
        #             {
        #                 "UserID": profile_data.get("UserID"),
        #                 "Username": profile_data.get("Username"),
        #                 "Avatar": profile_data.get("Avatar"),
        #                 "Banner": profile_data.get("Banner"),
        #                 "Biography": profile_data.get("Biography"),
        #                 "FollowersCount": profile_data.get("FollowersCount"),
        #                 "FollowingCount": profile_data.get("FollowingCount"),
        #                 "LikesCount": profile_data.get("LikesCount"),
        #                 "Name": profile_data.get("Name"),
        #             }
        #         )

        # print(f"CSV file '{csv_file_path}' has been created with agent profiles.")
        # for profile in profiles:

        virtuals_profiles = asyncio.run(fetch_agents_twitter_profiles())
        creatorbid_profiles = asyncio.run(fetch_creator_bid_agents_twitter_profiles())

        print(f"Length of virtuals_profiles: {len(virtuals_profiles)}")
        print(f"Length of creatorbid_profiles: {len(creatorbid_profiles)}")
        write_profiles_to_csv(
            virtuals_profiles=virtuals_profiles, creatorbid_profiles=creatorbid_profiles
        )

        # asyncio.run(upload_agent(creatorbid_profiles[0]))
        # print(profiles)  # Print the list of profiles

    except Exception as e:
        print(f"An error occurred: {e}")
