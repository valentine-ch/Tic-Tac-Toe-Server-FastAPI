import uuid
from fastapi import HTTPException


class InvitationManager:
    def __init__(self):
        self.invitations = {}

    def create_invitation(self, inviter: str, invited: str, grid_properties: dict,
                          inviter_playing_x: bool, play_again_scheme: str):
        invitation_id = str(uuid.uuid4())
        self.invitations[invitation_id] = {
            "inviter": inviter,
            "invited": invited,
            "grid_properties": grid_properties,
            "inviter_playing_x": inviter_playing_x,
            "play_again_scheme": play_again_scheme,
            "status": "pending",
            "game_id": None
        }
        return invitation_id

    def get_invitations(self, user: str):
        invitations = []
        for id, invitation in self.invitations.items():
            if invitation['invited'] == user and invitation['status'] == "pending":
                invitation_details = {
                    "invitation_id": id,
                    "inviter": invitation["inviter"],
                    "grid_properties": invitation["grid_properties"],
                    "inviter_playing_x": invitation["inviter_playing_x"],
                    "play_again_scheme": invitation["play_again_scheme"]
                }
                invitations.append(invitation_details)
        return invitations

    def get_sent_invitations(self, inviter: str):
        invitations = []
        for id, invitation in self.invitations.items():
            if invitation['inviter'] == inviter and invitation['status'] != "cancelled":
                invitation_details = {
                    "invitation_id": id,
                    "invited": invitation["invited"],
                    "grid_properties": invitation["grid_properties"],
                    "inviter_playing_x": invitation["inviter_playing_x"],
                    "play_again_scheme": invitation["play_again_scheme"],
                    "status": invitation["status"],
                    "game_id": invitation["game_id"]
                }
                invitations.append(invitation_details)
        return invitations

    def cancel_invitation(self, invitation_id: str, username: str):
        if invitation_id not in self.invitations:
            raise HTTPException(status_code=404, detail="Invitation not found")
        elif self.invitations[invitation_id]['inviter'] != username:
            raise HTTPException(status_code=403, detail="This invitation is not yours")
        elif self.invitations[invitation_id]['status'] == "cancelled":
            raise HTTPException(status_code=409, detail="Invitation already cancelled")
        elif self.invitations[invitation_id]['status'] == "accepted":
            raise HTTPException(status_code=409, detail="Invitation is accepted")
        else:
            self.invitations[invitation_id]['status'] = "cancelled"

    def decline_invitation(self, invitation_id: str, username: str):
        if invitation_id not in self.invitations:
            raise HTTPException(status_code=404, detail="Invitation not found")
        elif self.invitations[invitation_id]['invited'] != username:
            raise HTTPException(status_code=403, detail="This invitation is not for you")
        elif self.invitations[invitation_id]['status'] == "cancelled":
            raise HTTPException(status_code=410, detail="Invitation cancelled by inviter")
        elif self.invitations[invitation_id]['status'] != "pending":
            raise HTTPException(status_code=409, detail="Invitation already responded to")
        else:
            self.invitations[invitation_id]['status'] = "declined"

    def accept_invitation(self, invitation_id: str, game_id: str):
        if invitation_id in self.invitations:
            self.invitations[invitation_id]['status'] = "accepted"
            self.invitations[invitation_id]['game_id'] = game_id
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")

    def get_status(self, invitation_id: str, username: str):
        if invitation_id not in self.invitations:
            raise HTTPException(status_code=404, detail="Invitation not found")
        elif self.invitations[invitation_id]['inviter'] != username:
            raise HTTPException(status_code=403, detail="This invitation is not yours")
        else:
            return self.invitations[invitation_id]['status']

    def get_game_id(self, invitation_id: str):
        if invitation_id in self.invitations:
            return self.invitations[invitation_id]['game_id']
        else:
            raise HTTPException(status_code=404, detail="Invitation not found")
