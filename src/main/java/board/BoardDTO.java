package board;

public class BoardDTO {

	private int NUM;
	private String writer;
	private String email;
	private String SUBJECT;
	private String PASSWORD;
	private String reg_date;
	private int RE_STEP;
	private int RE_LEVEL;
	private int READCOUNT;
	private String CONTENT;
	private int REF;

	
	public int getNUM() {
		return NUM;
	}

	public void setNUM(int nUM) {
		NUM = nUM;
	}

	public String getWriter() {
		return writer;
	}

	public void setWriter(String writer) {
		this.writer = writer;
	}

	public String getEmail() {
		return email;
	}

	public void setEmail(String email) {
		this.email = email;
	}

	public String getSUBJECT() {
		return SUBJECT;
	}

	public void setSUBJECT(String sUBJECT) {
		SUBJECT = sUBJECT;
	}

	public String getPASSWORD() {
		return PASSWORD;
	}

	public void setPASSWORD(String pASSWORD) {
		PASSWORD = pASSWORD;
	}

	public String getReg_date() {
		return reg_date;
	}

	public void setReg_date(String reg_date) {
		this.reg_date = reg_date;
	}

	public int getREF() {
		return REF;
	}

	public void setREF(int rEF) {
		REF = rEF;
	}

	public int getRE_STEP() {
		return RE_STEP;
	}

	public void setRE_STEP(int rE_STEP) {
		RE_STEP = rE_STEP;
	}

	public int getRE_LEVEL() {
		return RE_LEVEL;
	}

	public void setRE_LEVEL(int rE_LEVEL) {
		RE_LEVEL = rE_LEVEL;
	}

	public int getREADCOUNT() {
		return READCOUNT;
	}

	public void setREADCOUNT(int rEADCOUNT) {
		READCOUNT = rEADCOUNT;
	}

	public String getCONTENT() {
		return CONTENT;
	}

	public void setCONTENT(String cONTENT) {
		CONTENT = cONTENT;
	}

	public BoardDTO() {

	}

}
