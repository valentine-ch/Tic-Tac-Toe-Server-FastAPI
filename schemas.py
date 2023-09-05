from pydantic import BaseModel


class GridProperties(BaseModel):
    size: int
    winning_line: int


class Invitation(BaseModel):
    invited: str
    grid_properties: GridProperties
    inviter_playing_x: bool
    play_again_scheme: str = "same"


class NewMove(BaseModel):
    game_id: str
    cell: str


class InvitationResponse(BaseModel):
    invitation_id: str
    response: str


class PlayAgain(BaseModel):
    game_id: str
    play_again: bool
