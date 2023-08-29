from pydantic import BaseModel


class GridProperties(BaseModel):
    size: int
    winning_line: int


class Invitation(BaseModel):
    invited: str
    grid_properties: GridProperties
    inviter_playing_x: bool


class NewMove(BaseModel):
    game_id: str
    cell: str


class InvitationResponse(BaseModel):
    invitation_id: str
    response: str
