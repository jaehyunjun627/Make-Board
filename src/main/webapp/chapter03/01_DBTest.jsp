<%@page import="java.sql.Connection"%>
<%@page import="java.sql.DriverManager"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>DB_Connect</title>
</head>
<body>
	<%
	//오라클 데이터 베이스 연결 url 설정
	String url = "jdbc:oracle:thin:@localhost:1521:xe";
	String user = "system";
	String pass = "12345";

	try {
		//1.오라클 드라이버 인식(ojdbc8.jar)
		Class.forName("oracle.jdbc.driver.OracleDriver");
		//2.오라클 접속
		Connection con = DriverManager.getConnection(url, user, pass);
	} catch (Exception e) {
		e.printStackTrace();
	}
	%>
	
	<h2>데이터베이스 연동 성공</h2>
</body>
</html>