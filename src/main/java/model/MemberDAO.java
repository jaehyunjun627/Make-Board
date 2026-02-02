package model;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.Vector;

public class MemberDAO {
   
   // 오라클 접속
   String url = "jdbc:oracle:thin:@localhost:1521:xe";
   String user = "system";
   String pass = "12345";
      
   Connection con; 
   PreparedStatement pstmt; 
   ResultSet rs; 
      
   // DB 연결
   public void getCon() {
      try {
         Class.forName("oracle.jdbc.driver.OracleDriver");
         con = DriverManager.getConnection(url, user, pass);
      } catch (Exception e) {
         e.printStackTrace();
      }
   }
      
   // 1. insert
   public void insertMember(MemberDTO mDTO) {
      try {
         getCon();
         String sql = "insert into member values(?,?,?,?,?,?,?,?,?,?,?)";
         pstmt = con.prepareStatement(sql);
            
         pstmt.setString(1, mDTO.getId());
         pstmt.setString(2, mDTO.getPass1());
         pstmt.setString(3, mDTO.getPass2());
         pstmt.setString(4, mDTO.getEmail());
         pstmt.setString(5, mDTO.getGender());
         pstmt.setString(6, mDTO.getAddress());
         pstmt.setString(7, mDTO.getPhone());
         pstmt.setString(8, mDTO.getHobby());
         pstmt.setString(9, mDTO.getJob());
         pstmt.setString(10, mDTO.getAge());
         pstmt.setString(11, mDTO.getInfo());

         pstmt.executeUpdate();
         con.close();
         
      } catch(Exception e) {
         e.printStackTrace();
      }
   }
      
   // 2. select (❗완성)
   public Vector<MemberDTO> allSelectMember() {
	    Vector<MemberDTO> v = new Vector<MemberDTO>();

	    try {
	        getCon();
	        String sql = "select * from member";
	        pstmt = con.prepareStatement(sql);
	        rs = pstmt.executeQuery();

	        while (rs.next()) { // ★ 여러 행이니까 while
	            MemberDTO dto = new MemberDTO();
	            dto.setId(rs.getString(1));
	            dto.setPass1(rs.getString(2));
	            dto.setPass2(rs.getString(3));
	            dto.setEmail(rs.getString(4));
	            dto.setGender(rs.getString(5));
	            dto.setAddress(rs.getString(6));
	            dto.setPhone(rs.getString(7));
	            dto.setHobby(rs.getString(8));
	            dto.setJob(rs.getString(9));
	            dto.setAge(rs.getString(10));
	            dto.setInfo(rs.getString(11));

	            v.add(dto);
	        }

	        con.close();
	    } catch (Exception e) {
	        e.printStackTrace();
	    }

	    return v;
	}
   
   public MemberDTO oneSelectMember(String id) {
	    MemberDTO bean = null;
	    try {
	        getCon();
	        String sql = "select * from member where id=?";
	        pstmt = con.prepareStatement(sql);
	        pstmt.setString(1, id);
	        rs = pstmt.executeQuery();

	        if (rs.next()) {
	            bean = new MemberDTO();
	            bean.setId(rs.getString(1));
	            bean.setPass1(rs.getString(2));
	            bean.setPass2(rs.getString(3));
	            bean.setEmail(rs.getString(4));
	            bean.setGender(rs.getString(5));
	            bean.setAddress(rs.getString(6));
	            bean.setPhone(rs.getString(7));
	            bean.setHobby(rs.getString(8));
	            bean.setJob(rs.getString(9));
	            bean.setAge(rs.getString(10));
	            bean.setInfo(rs.getString(11));
	        }
	        con.close();
	    } catch(Exception e) { e.printStackTrace(); }
	    return bean;
	}
   
   public void updateMember(MemberDTO bean){
       try {
           getCon();

           String sql = "update member set email=?, phone=?, address=? where id=?";

           pstmt = con.prepareStatement(sql);
           pstmt.setString(1, bean.getEmail());
           pstmt.setString(2, bean.getPhone());
           pstmt.setString(3, bean.getAddress());
           pstmt.setString(4, bean.getId());
           pstmt.executeUpdate();

           con.close();
       }
       catch (Exception e) {
           e.printStackTrace();
       }
       
   }
   
   public String getPass(String id) {
	    String pw = null;
	    try {
	        getCon();
	        String sql = "select pass1 from member where id=?";
	        pstmt = con.prepareStatement(sql);
	        pstmt.setString(1, id);
	        rs = pstmt.executeQuery();

	        if (rs.next()) {
	            pw = rs.getString(1);
	        }

	        con.close();
	    } catch (Exception e) {
	        e.printStackTrace();
	    }
	    return pw;
	}
   
   public void deleteMember(String id) {
	    try {
	        getCon();

	        String sql = "delete from member where id=?";
	        pstmt = con.prepareStatement(sql);
	        pstmt.setString(1, id);

	        pstmt.executeUpdate();

	        con.close();
	    } catch (Exception e) {
	        e.printStackTrace();
	    }
	}
}