package model;

public class LoginDAO {
    private String userid;
    private String password;

    // 🔥 기본 생성자 추가 필수!
    public LoginDAO() {}

    final String _userid = "myuser";
    final String _password = "12345";

    public boolean checkUser() {
        if(userid == null || userid.isEmpty() || password == null || password.isEmpty()) {
            System.out.println("전부 입력해주세요");
            return false;
        }
        if (userid.equals(_userid) && password.equals(_password)) {
            return true;
        }
        System.out.println("일치하지 않습니다");
        return false;
    }

    // Getter/Setter
    public String getUserid() { return userid; }
    public void setUserid(String userid) { this.userid = userid; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
}