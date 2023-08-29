import uuid
from fastapi import HTTPException


class InvitationManager:
    def __init__(self):
        self.invitations = {}

    def create_invitation(self, inviter: str, invited: str, grid_properties: dict, inviter_playing_x: bool):
        invitation_id = str(uuid.uuid4())
        self.invitations[invitation_id] = {
            "inviter": inviter,
            "invited": invited,
            "grid_properties": grid_properties,
            "inviter_playing_x": inviter_playing_x,
            "status": "pending",
            "game_id": None
        }
        return invitation_id

    # def get_invitations(self, user: str):
    #     return [id for id, invitation in self.invitations.items() if
    #             invitation['invited'] == user and invitation['status'] == "pending"]

    def get_invitations(self, user: str):
        invitations = []
        for id, invitation in self.invitations.items():
            if invitation['invited'] == user and invitation['status'] == "pending":
                invitation_details = {
                    "invitation_id": id,
                    "inviter": invitation["inviter"],
                    "grid_properties": invitation["grid_properties"],
                    "inviter_playing_x": invitation["inviter_playing_x"]
                }
                invitations.append(invitation_details)
        return invitations

    def cancel_invitation(self, invitation_id: str):
        if invitation_id in self.invitations:
            self.invitations[invitation_id]['status'] = "cancelled"
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")

    def decline_invitation(self, invitation_id: str):
        if invitation_id in self.invitations:
            self.invitations[invitation_id]['status'] = "declined"
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")

    def accept_invitation(self, invitation_id: str, game_id: str):
        if invitation_id in self.invitations:
            self.invitations[invitation_id]['status'] = "accepted"
            self.invitations[invitation_id]['game_id'] = game_id
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")

    def get_status(self, invitation_id: str):
        if invitation_id in self.invitations:
            return self.invitations[invitation_id]['status']
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")

    def get_game_id(self, invitation_id: str):
        if invitation_id in self.invitations:
            return self.invitations[invitation_id]['game_id']
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")
